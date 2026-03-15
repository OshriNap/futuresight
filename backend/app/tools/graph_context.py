"""Graph Context Tool — uses the event causality graph to inform predictions.

Queries the event graph for connected events. If connected events have
resolved with known outcomes, uses them as additional signals.
"""

import logging

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)

# Relationship direction multipliers
# "causes" means source event happening makes target more likely
REL_MULTIPLIERS = {
    "causes": 1.0,
    "amplifies": 0.7,
    "correlates": 0.5,
    "precedes": 0.3,
    "mitigates": -0.7,
}


class GraphContextTool(BasePredictionTool):
    name = "graph_context"
    tool_type = "heuristic"
    description = "Uses event causality graph to find related resolved events that inform the prediction."
    best_for = ["geopolitics", "economy", "politics"]

    async def predict(self, input: ToolInput) -> ToolOutput:
        market_prob = input.current_signals.get("market_probability", 0.5)
        source_id = input.metadata.get("source_id")

        if not source_id:
            return ToolOutput(
                probability=market_prob,
                confidence=0.1,
                reasoning="No source_id for graph lookup",
                signals_used=["market_probability"],
            )

        # Query graph for connected events
        from sqlalchemy import select, or_
        from app.database import async_session
        from app.models.event_graph import EventEdge, EventNode
        from app.models.source import Source

        connected_events = []

        async with async_session() as db:
            # Find the event node for this source
            node_result = await db.execute(
                select(EventNode).where(EventNode.source_id == source_id)
            )
            node = node_result.scalar_one_or_none()

            if not node:
                return ToolOutput(
                    probability=market_prob,
                    confidence=0.1,
                    reasoning="No event node found for this source",
                    signals_used=["market_probability"],
                )

            # Get connected edges (both incoming and outgoing)
            edges_result = await db.execute(
                select(EventEdge).where(
                    or_(
                        EventEdge.source_node_id == node.id,
                        EventEdge.target_node_id == node.id,
                    )
                )
            )
            edges = edges_result.scalars().all()

            if not edges:
                return ToolOutput(
                    probability=market_prob,
                    confidence=0.15,
                    reasoning="No graph connections found",
                    signals_used=["market_probability"],
                )

            # Look up connected nodes and their source resolution status
            for edge in edges:
                other_id = edge.target_node_id if edge.source_node_id == node.id else edge.source_node_id
                is_outgoing = edge.source_node_id == node.id

                other_node_result = await db.execute(
                    select(EventNode).where(EventNode.id == other_id)
                )
                other_node = other_node_result.scalar_one_or_none()
                if not other_node:
                    continue

                # Check if connected event's source has been resolved
                resolved_outcome = None
                if other_node.source_id:
                    source_result = await db.execute(
                        select(Source).where(Source.id == other_node.source_id)
                    )
                    connected_source = source_result.scalar_one_or_none()
                    if connected_source and connected_source.actual_outcome:
                        resolved_outcome = connected_source.actual_outcome

                connected_events.append({
                    "title": other_node.title[:80],
                    "relationship": edge.relationship_type,
                    "strength": edge.strength,
                    "is_outgoing": is_outgoing,
                    "confidence": other_node.confidence,
                    "resolved_outcome": resolved_outcome,
                    "status": other_node.status,
                })

        if not connected_events:
            return ToolOutput(
                probability=market_prob,
                confidence=0.15,
                reasoning="Graph connections found but no useful signal",
                signals_used=["market_probability"],
            )

        # Compute adjustment from connected events
        adjustment = 0.0
        evidence_parts = []

        for event in connected_events:
            rel_mult = REL_MULTIPLIERS.get(event["relationship"], 0.3)

            if event["resolved_outcome"]:
                # Resolved events give strong signal
                outcome_val = 1.0 if event["resolved_outcome"] in ("yes",) else -1.0
                signal = outcome_val * rel_mult * event["strength"] * 0.1
                adjustment += signal
                evidence_parts.append(
                    f"{event['title'][:40]} resolved={event['resolved_outcome']} "
                    f"({event['relationship']}, {signal:+.3f})"
                )
            elif event["confidence"] is not None:
                # Unresolved but with probability — weaker signal
                # If connected event is likely (>0.7) and "causes" this one, nudge up
                prob_signal = (event["confidence"] - 0.5) * rel_mult * event["strength"] * 0.05
                adjustment += prob_signal
                evidence_parts.append(
                    f"{event['title'][:40]} prob={event['confidence']:.0%} "
                    f"({event['relationship']}, {prob_signal:+.3f})"
                )

        adjusted_prob = max(0.02, min(0.98, market_prob + adjustment))

        confidence = min(0.5, 0.15 + len(connected_events) * 0.05)

        reasoning = (
            f"Graph context: {len(connected_events)} connected events, "
            f"net adjustment={adjustment:+.3f}. "
            + "; ".join(evidence_parts[:3])
        )

        return ToolOutput(
            probability=adjusted_prob,
            confidence=confidence,
            reasoning=reasoning,
            signals_used=["market_probability", "event_graph"],
            metadata={
                "connected_events": len(connected_events),
                "resolved_events": sum(1 for e in connected_events if e["resolved_outcome"]),
                "adjustment": round(adjustment, 4),
            },
        )

    def get_required_signals(self) -> list[str]:
        return ["market_probability"]

    def can_handle(self, input: ToolInput) -> tuple[bool, str]:
        if "market_probability" not in input.current_signals:
            return False, "Missing market_probability"
        if not input.metadata.get("source_id"):
            return False, "No source_id for graph lookup"
        return True, "ok"
