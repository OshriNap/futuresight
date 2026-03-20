"""Event graph builder — creates nodes and causal edges from collected data.

Extracts events from high-signal sources and links related events.
Only creates edges when there's strong topical overlap, not loose keyword matches.
"""

import logging
import re

from sqlalchemy import select

from app.database import async_session
from app.models.event_graph import EventEdge, EventNode
from app.models.source import Source

logger = logging.getLogger(__name__)

# Category → event_type mapping
TYPE_MAP = {
    "geopolitics": "geopolitical", "politics": "geopolitical",
    "economy": "economic", "finance": "economic",
    "technology": "tech", "science": "tech",
    "climate": "environmental", "health": "social",
    "security": "geopolitical", "military": "geopolitical",
    "society": "social", "general": "social",
}

# Causal patterns: (source_keywords, target_keywords, relationship_type)
# Both source AND target must match AT LEAST 2 keywords for an edge
CAUSAL_PATTERNS = [
    (["sanction", "tariff", "trade war", "embargo"],
     ["oil price", "inflation", "economic", "gdp", "recession", "economy"],
     "causes"),
    (["war", "invasion", "military", "attack", "strike"],
     ["oil", "energy", "refugee", "humanitarian", "civilian"],
     "causes"),
    (["election", "vote", "primary", "nominee"],
     ["policy", "legislation", "regulation", "executive order"],
     "precedes"),
    (["fed", "federal reserve", "interest rate", "monetary policy"],
     ["stock market", "housing", "mortgage", "bond", "treasury"],
     "causes"),
    (["climate change", "global warming", "emissions", "carbon"],
     ["weather", "hurricane", "drought", "flood", "wildfire", "sea level"],
     "amplifies"),
    (["pandemic", "outbreak", "virus", "covid", "measles"],
     ["vaccine", "quarantine", "travel ban", "health care", "hospital"],
     "causes"),
    (["oil", "opec", "crude", "petroleum", "energy price"],
     ["gas price", "inflation", "transport", "airline", "shipping"],
     "causes"),
    (["cyber attack", "hack", "data breach", "ransomware"],
     ["cybersecurity", "regulation", "privacy law", "security"],
     "precedes"),
    (["ai", "artificial intelligence", "chatgpt", "openai", "llm"],
     ["job", "automation", "regulation", "productivity", "workforce"],
     "amplifies"),
    (["bitcoin", "crypto", "ethereum", "cryptocurrency"],
     ["regulation", "sec", "financial", "exchange", "defi"],
     "correlates"),
    (["ukraine", "russia", "zelenskyy", "putin", "moscow"],
     ["nato", "europe", "defense", "weapons", "aid"],
     "causes"),
    (["iran", "tehran", "nuclear"],
     ["sanctions", "oil", "middle east", "israel"],
     "amplifies"),
    (["china", "beijing", "xi jinping"],
     ["taiwan", "trade", "tariff", "semiconductor", "supply chain"],
     "amplifies"),
]

STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "is", "are", "was", "were",
    "will", "be", "by", "from", "with", "has", "have", "had", "its", "it", "this", "that",
    "and", "or", "but", "not", "no", "as", "if", "than", "more", "most", "also", "about",
    "says", "said", "new", "could", "would", "may", "after", "over", "into", "up", "out",
    "just", "can", "been", "how", "what", "why", "who", "where", "when", "between",
}


def _extract_terms(title: str) -> set[str]:
    """Extract meaningful multi-word and single-word terms."""
    lower = title.lower()
    # Single words minus stop words
    words = {w for w in re.findall(r'[a-z]+', lower) if w not in STOP_WORDS and len(w) > 3}
    return words


def _match_score(text: str, keywords: list[str]) -> int:
    """Count how many keywords match in the text. Supports multi-word keywords."""
    lower = text.lower()
    return sum(1 for kw in keywords if kw in lower)


def _detect_event_type(title: str, category: str | None) -> str:
    # Try mapped category first, but skip slugs that aren't real categories
    if category and category in TYPE_MAP:
        return TYPE_MAP[category]
    # Keyword-based detection
    lower = title.lower()
    if any(w in lower for w in ["war", "invasion", "military", "nato", "sanction", "attack",
                                 "nuclear", "missile", "ceasefire", "troops", "iran", "russia",
                                 "ukraine", "china", "taiwan", "putin", "zelenskyy", "regime"]):
        return "geopolitical"
    if any(w in lower for w in ["election", "vote", "senate", "governor", "president",
                                 "democrat", "republican", "nominee", "congress", "parliament"]):
        return "geopolitical"
    if any(w in lower for w in ["gdp", "inflation", "economy", "fed", "trade", "tariff",
                                 "recession", "interest rate", "market cap", "stock", "bitcoin",
                                 "ethereum", "crypto", "ipo", "price", "currency", "bond"]):
        return "economic"
    if any(w in lower for w in ["ai", "tech", "software", "cyber", "chip", "quantum",
                                 "openai", "google", "apple", "semiconductor", "llm", "robot"]):
        return "tech"
    if any(w in lower for w in ["climate", "emissions", "hurricane", "wildfire", "carbon",
                                 "temperature", "weather", "drought", "flood", "sea level"]):
        return "environmental"
    return "social"


async def build_event_graph() -> dict:
    """Build event nodes from sources and find causal relationships.

    Only creates edges when there's strong topical overlap (2+ keyword matches).
    """
    nodes_created = 0
    edges_created = 0

    async with async_session() as db:
        # Get sources worth tracking
        from app.tasks.prediction_tasks import _is_sports_or_entertainment

        poly_sources = await db.execute(
            select(Source)
            .where(Source.platform.in_(["polymarket", "manifold"]))
            .where(Source.current_market_probability.isnot(None))
            .order_by(Source.updated_at.desc())
            .limit(200)
        )

        news_sources = await db.execute(
            select(Source)
            .where(Source.platform.in_(["gdelt", "reddit"]))
            .order_by(Source.updated_at.desc())
            .limit(200)
        )

        all_sources = list(poly_sources.scalars().all()) + list(news_sources.scalars().all())

        # Filter junk
        filtered = []
        for s in all_sources:
            if s.platform == "polymarket":
                raw = s.raw_data or {}
                if _is_sports_or_entertainment(s.title, raw.get("slug", "")):
                    continue
                if raw.get("liquidityNum", 0) < 500:
                    continue
            # Skip very short or generic titles
            if len(s.title) < 20:
                continue
            filtered.append(s)

        # Get existing nodes
        existing_nodes = await db.execute(select(EventNode))
        existing_by_source = {n.source_id: n for n in existing_nodes.scalars().all() if n.source_id}

        # Create nodes
        new_nodes = []
        for source in filtered:
            if source.id in existing_by_source:
                continue

            event_type = _detect_event_type(source.title, source.category)
            confidence = source.current_market_probability if source.platform == "polymarket" else None

            node = EventNode(
                title=source.title[:500],
                description=(source.description or "")[:500] or None,
                category=source.category,
                event_type=event_type,
                source_id=source.id,
                confidence=confidence,
                status="active",
            )
            db.add(node)
            new_nodes.append(node)
            nodes_created += 1

        if new_nodes:
            await db.flush()

        # Get all nodes for edge detection
        all_nodes_result = await db.execute(select(EventNode).limit(500))
        all_nodes = all_nodes_result.scalars().all()

        if len(all_nodes) < 2:
            await db.commit()
            return {"nodes_created": nodes_created, "edges_created": 0}

        # Get existing edges
        existing_edges = await db.execute(select(EventEdge))
        existing_edge_pairs = {
            (e.source_node_id, e.target_node_id)
            for e in existing_edges.scalars().all()
        }

        # Find causal relationships — require strong matches
        for pattern_src_kws, pattern_tgt_kws, rel_type in CAUSAL_PATTERNS:
            # Find nodes matching source pattern (2+ keywords)
            src_matches = [(n, _match_score(n.title, pattern_src_kws))
                          for n in all_nodes]
            src_matches = [(n, s) for n, s in src_matches if s >= 1]

            # Find nodes matching target pattern (2+ keywords)
            tgt_matches = [(n, _match_score(n.title, pattern_tgt_kws))
                          for n in all_nodes]
            tgt_matches = [(n, s) for n, s in tgt_matches if s >= 1]

            for src_node, src_score in src_matches:
                for tgt_node, tgt_score in tgt_matches:
                    if src_node.id == tgt_node.id:
                        continue
                    if (src_node.id, tgt_node.id) in existing_edge_pairs:
                        continue

                    # Require combined score of at least 2
                    combined = src_score + tgt_score
                    if combined < 2:
                        continue

                    # Additional check: nodes should share some topical terms
                    src_terms = _extract_terms(src_node.title)
                    tgt_terms = _extract_terms(tgt_node.title)
                    shared = src_terms & tgt_terms
                    # Either share terms OR strongly match the pattern
                    if not shared and combined < 3:
                        continue

                    strength = min(0.9, 0.3 + combined * 0.1 + len(shared) * 0.05)

                    src_kw_str = "/".join(k for k in pattern_src_kws[:3] if k in src_node.title.lower())
                    tgt_kw_str = "/".join(k for k in pattern_tgt_kws[:3] if k in tgt_node.title.lower())
                    reasoning = f"{src_kw_str} {rel_type} {tgt_kw_str}"

                    edge = EventEdge(
                        source_node_id=src_node.id,
                        target_node_id=tgt_node.id,
                        relationship_type=rel_type,
                        strength=strength,
                        reasoning=reasoning,
                        detected_by="agent",
                    )
                    db.add(edge)
                    existing_edge_pairs.add((src_node.id, tgt_node.id))
                    edges_created += 1

        await db.commit()

    logger.info(f"Event graph: nodes_created={nodes_created}, edges_created={edges_created}")
    return {"nodes_created": nodes_created, "edges_created": edges_created}
