"""Event graph builder — creates nodes and causal edges from collected data.

Uses MiniLM embeddings for semantic similarity and NLI cross-encoder for
causal relationship classification. Dynamic knee-based thresholding separates
signal from noise in the similarity distribution.
"""

import logging

import numpy as np
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


def find_knee_threshold(similarities: np.ndarray, fallback: float = 0.65) -> float:
    """Find the knee point in the similarity distribution."""
    if len(similarities) < 5:
        return fallback

    sorted_sims = np.sort(similarities)[::-1]

    if len(sorted_sims) > 10_000:
        indices = np.linspace(0, len(sorted_sims) - 1, 10_000, dtype=int)
        sorted_sims = sorted_sims[indices]

    try:
        from kneed import KneeLocator
        kl = KneeLocator(
            range(len(sorted_sims)),
            sorted_sims,
            curve="convex",
            direction="decreasing",
            interp_method="interp1d",
        )
        if kl.knee is not None:
            knee_value = float(sorted_sims[kl.knee])
            if 0.2 < knee_value < 0.95:
                return knee_value
    except Exception:
        pass

    return fallback


def classify_relationship(nli_scores: dict[str, float]) -> str:
    """Map NLI scores to a relationship type."""
    ent = nli_scores.get("entailment", 0)
    con = nli_scores.get("contradiction", 0)

    if con > 0.5:
        return "mitigates"
    if ent > 0.8:
        return "causes"
    if ent > 0.5:
        return "amplifies"
    if ent > 0.3:
        return "correlates"
    return "precedes"


def build_candidate_pairs(
    embeddings: np.ndarray, threshold: float
) -> list[tuple[int, int, float]]:
    """Find all pairs of nodes with cosine similarity above threshold."""
    n = len(embeddings)
    if n < 2:
        return []

    sim_matrix = embeddings @ embeddings.T
    i_indices, j_indices = np.triu_indices(n, k=1)
    sims = sim_matrix[i_indices, j_indices]

    mask = sims >= threshold
    pairs = [
        (int(i_indices[k]), int(j_indices[k]), float(sims[k]))
        for k in np.where(mask)[0]
    ]

    return pairs


# Lazy-loaded NLI pipeline (shared with nli_tool.py)
_nli_pipeline = None


def _get_nli_pipeline():
    global _nli_pipeline
    if _nli_pipeline is None:
        import torch
        from transformers import pipeline as hf_pipeline

        device = 0 if torch.cuda.is_available() else -1
        logger.info(f"Loading NLI model for graph edges on {'GPU' if device == 0 else 'CPU'}...")
        _nli_pipeline = hf_pipeline(
            "zero-shot-classification",
            model="cross-encoder/nli-distilroberta-base",
            device=device,
        )
        logger.info("NLI model loaded for graph edges.")
    return _nli_pipeline


def run_nli_causal(pairs: list[tuple[str, str]]) -> list[dict[str, float]]:
    """Run NLI inference on (source_title, target_title) pairs.

    For each pair, tests "The first event led to the second event"
    and returns entailment/contradiction/neutral scores.
    """
    if not pairs:
        return []

    pipe = _get_nli_pipeline()
    results = []

    for src_title, tgt_title in pairs:
        premise = f"{src_title}. {tgt_title}."
        try:
            output = pipe(
                premise,
                candidate_labels=["entailment", "contradiction", "neutral"],
                hypothesis_template="{}",
            )
            label_scores = dict(zip(output["labels"], output["scores"]))
            results.append({
                "entailment": label_scores.get("entailment", 0),
                "contradiction": label_scores.get("contradiction", 0),
                "neutral": label_scores.get("neutral", 0),
            })
        except Exception as e:
            logger.warning(f"NLI causal failed for pair: {e}")
            results.append({"entailment": 0, "contradiction": 0, "neutral": 1.0})

    return results


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
    """Build event nodes from sources and find causal edges via embeddings + NLI.

    1. Create nodes from new high-signal sources
    2. Compute embeddings for new nodes
    3. Find candidate pairs using knee-detected similarity threshold
    4. Classify relationships via NLI
    5. Create edges with temporal ordering
    """
    import asyncio
    from app.tasks.embedding_tasks import _compute_embeddings

    nodes_created = 0
    edges_created = 0
    threshold = 0.65  # default, will be overwritten by knee detection

    async with async_session() as db:
        # --- Node creation (unchanged logic) ---
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

        filtered = []
        for s in all_sources:
            if s.platform == "polymarket":
                raw = s.raw_data or {}
                if _is_sports_or_entertainment(s.title, raw.get("slug", "")):
                    continue
                if raw.get("liquidityNum", 0) < 500:
                    continue
            if len(s.title) < 20:
                continue
            filtered.append(s)

        existing_nodes = await db.execute(select(EventNode))
        existing_by_source = {n.source_id: n for n in existing_nodes.scalars().all() if n.source_id}

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

        # --- Edge creation via embeddings + NLI ---
        if not new_nodes:
            await db.commit()
            return {"nodes_created": 0, "edges_created": 0}

        # Load all existing nodes for cross-comparison
        all_nodes_result = await db.execute(select(EventNode))
        all_nodes = list(all_nodes_result.scalars().all())

        if len(all_nodes) < 2:
            await db.commit()
            return {"nodes_created": nodes_created, "edges_created": 0}

        node_list = all_nodes
        new_node_ids = {n.id for n in new_nodes}

        # Compute embeddings for all nodes
        titles = [n.title for n in node_list]
        embeddings = await asyncio.to_thread(_compute_embeddings, titles)

        # Compute similarities: new nodes vs all nodes
        new_indices = [i for i, n in enumerate(node_list) if n.id in new_node_ids]
        if not new_indices:
            await db.commit()
            return {"nodes_created": nodes_created, "edges_created": 0}

        new_embs = embeddings[new_indices]
        all_sims = new_embs @ embeddings.T

        # Collect all similarity scores for knee detection
        all_sim_scores = []
        for row_idx in range(len(new_indices)):
            new_i = new_indices[row_idx]
            for j in range(len(node_list)):
                if new_i != j:
                    all_sim_scores.append(all_sims[row_idx, j])

        all_sim_scores = np.array(all_sim_scores)
        threshold = find_knee_threshold(all_sim_scores)
        logger.info(f"Graph edge threshold (knee): {threshold:.3f}")

        # Build candidate pairs above threshold
        existing_edges = await db.execute(select(EventEdge))
        existing_edge_pairs = {
            (e.source_node_id, e.target_node_id)
            for e in existing_edges.scalars().all()
        }
        existing_edge_pairs |= {(b, a) for a, b in existing_edge_pairs}

        candidates = []
        for row_idx in range(len(new_indices)):
            new_i = new_indices[row_idx]
            for j in range(len(node_list)):
                if new_i == j:
                    continue
                sim = float(all_sims[row_idx, j])
                if sim < threshold:
                    continue
                node_a = node_list[new_i]
                node_b = node_list[j]
                if (node_a.id, node_b.id) in existing_edge_pairs:
                    continue
                if (node_b.id, node_a.id) in existing_edge_pairs:
                    continue

                # Temporal ordering: earlier -> source, later -> target
                time_a = node_a.occurred_at or node_a.created_at
                time_b = node_b.occurred_at or node_b.created_at
                if time_a and time_b and time_a <= time_b:
                    src_node, tgt_node = node_a, node_b
                elif time_a and time_b:
                    src_node, tgt_node = node_b, node_a
                else:
                    if node_a.title <= node_b.title:
                        src_node, tgt_node = node_a, node_b
                    else:
                        src_node, tgt_node = node_b, node_a

                candidates.append((src_node, tgt_node, sim))

        if not candidates:
            await db.commit()
            return {"nodes_created": nodes_created, "edges_created": 0}

        # Cap candidates to limit NLI calls
        candidates.sort(key=lambda x: x[2], reverse=True)
        candidates = candidates[:500]

        # Run NLI classification
        nli_pairs = [(c[0].title, c[1].title) for c in candidates]
        nli_results = await asyncio.to_thread(run_nli_causal, nli_pairs)

        # Create edges
        for (src_node, tgt_node, sim), nli_scores in zip(candidates, nli_results):
            rel_type = classify_relationship(nli_scores)
            ent_score = nli_scores.get("entailment", 0)
            strength = round(ent_score * sim, 3)

            if strength < 0.1:
                continue

            edge = EventEdge(
                source_node_id=src_node.id,
                target_node_id=tgt_node.id,
                relationship_type=rel_type,
                strength=strength,
                reasoning=f"Semantic similarity: {sim:.2f}, NLI entailment: {ent_score:.2f}",
                detected_by="agent",
            )
            db.add(edge)
            existing_edge_pairs.add((src_node.id, tgt_node.id))
            edges_created += 1

        await db.commit()

    logger.info(f"Event graph: nodes={nodes_created}, edges={edges_created}, threshold={threshold:.3f}")
    return {"nodes_created": nodes_created, "edges_created": edges_created, "threshold": round(threshold, 3)}


async def backfill_graph_edges(batch_size: int = 500) -> dict:
    """One-time backfill: process all existing nodes to create edges.

    Processes nodes in batches. For each batch, computes embeddings,
    finds candidates via knee threshold, classifies via NLI, creates edges.
    """
    import asyncio
    from app.tasks.embedding_tasks import _compute_embeddings

    total_edges = 0
    batches_processed = 0

    async with async_session() as db:
        all_nodes_result = await db.execute(
            select(EventNode).order_by(EventNode.created_at.asc())
        )
        all_nodes = list(all_nodes_result.scalars().all())
        logger.info(f"Backfill: {len(all_nodes)} total nodes")

        if len(all_nodes) < 2:
            return {"total_edges": 0, "batches": 0, "total_nodes": len(all_nodes)}

        titles = [n.title for n in all_nodes]
        embeddings = await asyncio.to_thread(_compute_embeddings, titles)

        existing_edges = await db.execute(select(EventEdge))
        existing_edge_pairs = set()
        for e in existing_edges.scalars().all():
            existing_edge_pairs.add((e.source_node_id, e.target_node_id))
            existing_edge_pairs.add((e.target_node_id, e.source_node_id))

        for batch_start in range(0, len(all_nodes), batch_size):
            batch_end = min(batch_start + batch_size, len(all_nodes))
            batch_embs = embeddings[batch_start:batch_end]

            sims = batch_embs @ embeddings.T

            sim_scores = []
            for row_idx in range(len(batch_embs)):
                global_i = batch_start + row_idx
                for j in range(len(all_nodes)):
                    if global_i != j and global_i < j:
                        sim_scores.append(sims[row_idx, j])

            if not sim_scores:
                continue

            threshold = find_knee_threshold(np.array(sim_scores))
            logger.info(f"Backfill batch {batches_processed}: threshold={threshold:.3f}")

            candidates = []
            for row_idx in range(len(batch_embs)):
                global_i = batch_start + row_idx
                for j in range(len(all_nodes)):
                    if global_i >= j:
                        continue
                    sim = float(sims[row_idx, j])
                    if sim < threshold:
                        continue

                    node_a = all_nodes[global_i]
                    node_b = all_nodes[j]

                    if (node_a.id, node_b.id) in existing_edge_pairs:
                        continue

                    time_a = node_a.occurred_at or node_a.created_at
                    time_b = node_b.occurred_at or node_b.created_at
                    if time_a and time_b and time_a <= time_b:
                        src_node, tgt_node = node_a, node_b
                    elif time_a and time_b:
                        src_node, tgt_node = node_b, node_a
                    else:
                        if node_a.title <= node_b.title:
                            src_node, tgt_node = node_a, node_b
                        else:
                            src_node, tgt_node = node_b, node_a

                    candidates.append((src_node, tgt_node, sim))

            if not candidates:
                batches_processed += 1
                continue

            candidates.sort(key=lambda x: x[2], reverse=True)
            candidates = candidates[:500]

            nli_pairs = [(c[0].title, c[1].title) for c in candidates]
            nli_results = await asyncio.to_thread(run_nli_causal, nli_pairs)

            batch_edges = 0
            for (src_node, tgt_node, sim), nli_scores in zip(candidates, nli_results):
                rel_type = classify_relationship(nli_scores)
                ent_score = nli_scores.get("entailment", 0)
                strength = round(ent_score * sim, 3)

                if strength < 0.1:
                    continue

                edge = EventEdge(
                    source_node_id=src_node.id,
                    target_node_id=tgt_node.id,
                    relationship_type=rel_type,
                    strength=strength,
                    reasoning=f"Semantic similarity: {sim:.2f}, NLI entailment: {ent_score:.2f}",
                    detected_by="agent",
                )
                db.add(edge)
                existing_edge_pairs.add((src_node.id, tgt_node.id))
                existing_edge_pairs.add((tgt_node.id, src_node.id))
                batch_edges += 1

            await db.flush()
            total_edges += batch_edges
            batches_processed += 1
            logger.info(f"Backfill batch {batches_processed}: {batch_edges} edges created")

        await db.commit()

    logger.info(f"Backfill complete: {total_edges} edges across {batches_processed} batches")
    return {
        "total_edges": total_edges,
        "batches": batches_processed,
        "total_nodes": len(all_nodes),
    }
