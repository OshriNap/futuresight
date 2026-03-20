"""Feature Ideator Meta-Agent

Analyzes data quality, coverage gaps, and source freshness.
Surfaces actionable observations to the scratchpad for Claude Code tasks to review.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.agents.meta.base_meta import BaseMetaAgent
from app.database import async_session
from app.models.event_graph import EventEdge, EventNode
from app.models.prediction import Prediction
from app.models.source import Source

logger = logging.getLogger(__name__)


class FeatureIdeator(BaseMetaAgent):
    agent_type = "feature_ideator"

    async def think(self) -> dict:
        """Analyze data quality, coverage gaps, and graph connectivity."""
        actions = []
        scratchpad_entries = []
        now = datetime.now(timezone.utc)

        async with async_session() as db:
            # 1. Source freshness — how stale is our data?
            platforms = ["polymarket", "manifold", "gdelt", "reddit"]
            freshness_lines = []
            stale_platforms = []
            for platform in platforms:
                result = await db.execute(
                    select(func.max(Source.updated_at))
                    .where(Source.platform == platform)
                )
                latest = result.scalar()
                if latest:
                    age = now - latest.replace(tzinfo=timezone.utc)
                    hours = age.total_seconds() / 3600
                    freshness_lines.append(f"  {platform}: last update {hours:.1f}h ago")
                    if hours > 12:
                        stale_platforms.append(platform)
                else:
                    freshness_lines.append(f"  {platform}: no data")
                    stale_platforms.append(platform)

            scratchpad_entries.append({
                "title": "Data Freshness Report",
                "content": "\n".join(freshness_lines),
                "category": "data_quality",
                "priority": "high" if stale_platforms else "low",
                "tags": ["freshness", "data_quality"] + stale_platforms,
            })
            if stale_platforms:
                actions.append(f"Stale platforms: {', '.join(stale_platforms)}")

            # 2. Category coverage — which categories have few predictions?
            result = await db.execute(
                select(Source.category, func.count(Source.id))
                .where(Source.signal_type == "market_probability")
                .group_by(Source.category)
                .order_by(func.count(Source.id).desc())
            )
            cat_counts = result.all()
            coverage_lines = [f"  {cat or 'uncategorized'}: {cnt} markets" for cat, cnt in cat_counts]
            total_markets = sum(cnt for _, cnt in cat_counts)

            # Find underrepresented categories
            expected = ["economy", "technology", "geopolitics", "politics", "finance", "climate", "health"]
            present = {cat for cat, _ in cat_counts if cat}
            missing = [c for c in expected if c not in present]

            content = "\n".join(coverage_lines)
            if missing:
                content += f"\n\nMissing categories: {', '.join(missing)}"
                content += "\nConsider adding user interests for these topics."

            scratchpad_entries.append({
                "title": "Category Coverage Analysis",
                "content": content,
                "category": "coverage",
                "priority": "medium" if missing else "low",
                "tags": ["categories", "coverage"],
            })
            actions.append(f"Market coverage: {total_markets} markets across {len(cat_counts)} categories")

            # 3. Sentiment coverage — how many sources have sentiment in raw_data?
            total_sources = (await db.execute(select(func.count(Source.id)))).scalar() or 0
            result = await db.execute(select(Source.raw_data))
            scored_sentiment = sum(
                1 for (rd,) in result.all()
                if rd and rd.get("sentiment_label") is not None
            )
            coverage_pct = (scored_sentiment / total_sources * 100) if total_sources else 0
            actions.append(f"Sentiment coverage: {scored_sentiment}/{total_sources} ({coverage_pct:.0f}%)")

            # 4. Graph connectivity
            node_count = (await db.execute(select(func.count(EventNode.id)))).scalar() or 0
            edge_count = (await db.execute(select(func.count(EventEdge.id)))).scalar() or 0

            if node_count > 0:
                # Find isolated nodes (no edges)
                connected_ids = set()
                edges_result = await db.execute(select(EventEdge.source_node_id, EventEdge.target_node_id))
                for src_id, tgt_id in edges_result.all():
                    connected_ids.add(src_id)
                    connected_ids.add(tgt_id)

                isolated = node_count - len(connected_ids)
                connectivity = len(connected_ids) / node_count * 100 if node_count else 0

                # Edge type breakdown
                edge_types = await db.execute(
                    select(EventEdge.relationship_type, func.count(EventEdge.id))
                    .group_by(EventEdge.relationship_type)
                )
                type_lines = [f"  {t}: {c}" for t, c in edge_types.all()]

                scratchpad_entries.append({
                    "title": "Graph Connectivity Report",
                    "content": (
                        f"Nodes: {node_count}, Edges: {edge_count}\n"
                        f"Connected nodes: {len(connected_ids)} ({connectivity:.0f}%)\n"
                        f"Isolated nodes: {isolated}\n"
                        f"Avg edges per connected node: {edge_count * 2 / max(len(connected_ids), 1):.1f}\n\n"
                        f"Edge types:\n" + "\n".join(type_lines)
                    ),
                    "category": "graph",
                    "priority": "medium" if connectivity < 30 else "low",
                    "tags": ["graph", "connectivity"],
                })
                actions.append(f"Graph: {node_count} nodes, {edge_count} edges, {connectivity:.0f}% connected")

            # 5. Predictions without matched sources
            preds_no_match = (await db.execute(
                select(func.count(Prediction.id))
                .join(Source, Prediction.source_id == Source.id)
                .where(Source.signal_type == "market_probability")
            )).scalar() or 0

            market_sources_with_matches = (await db.execute(
                select(func.count(Source.id))
                .where(Source.signal_type == "market_probability")
                .where(Source.raw_data["matched_sources"].isnot(None))
            )).scalar() or 0

            actions.append(f"Markets with news matches: {market_sources_with_matches}/{total_markets}")

        summary = f"Feature analysis: {len(scratchpad_entries)} insights, {len(actions)} observations"
        return {
            "summary": summary,
            "actions": actions,
            "scratchpad_entries": scratchpad_entries,
        }
