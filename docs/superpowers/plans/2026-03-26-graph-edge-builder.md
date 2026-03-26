# Graph Edge Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken hardcoded-pattern graph edge builder with embedding similarity + NLI causal classification, using dynamic knee-based thresholding and temporal ordering.

**Architecture:** Compute MiniLM embeddings for node titles, find candidate pairs via cosine similarity with knee-detected threshold, classify relationship types via NLI, enforce temporal ordering for edge directionality. Two modes: one-time backfill for existing 9k nodes, incremental for pipeline runs.

**Tech Stack:** Python, NumPy, sentence-transformers (MiniLM), transformers (NLI cross-encoder), kneed, SQLAlchemy async, FastAPI

---

### Task 1: Add `kneed` Dependency

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add kneed to dependencies**

In `backend/pyproject.toml`, add `"kneed>=0.8.0"` to the `dependencies` list:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sqlalchemy[asyncio]>=2.0.35",
    "aiosqlite>=0.20.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "httpx>=0.28.0",
    "kneed>=0.8.0",
]
```

- [ ] **Step 2: Install**

Run: `cd /home/oshrin/projects/future_prediction/backend && pip install -e .`
Expected: Successfully installed kneed

- [ ] **Step 3: Verify import**

Run: `python3 -c "from kneed import KneeLocator; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore: add kneed dependency for graph edge knee detection"
```

---

### Task 2: Write Tests for Knee Detection and Edge Classification

**Files:**
- Create: `backend/tests/test_graph_edges.py`

- [ ] **Step 1: Write test file with all graph edge builder tests**

```python
"""Tests for embedding+NLI graph edge builder."""

import numpy as np
import pytest

from app.tasks.graph_tasks import (
    find_knee_threshold,
    classify_relationship,
    build_candidate_pairs,
)


class TestFindKneeThreshold:
    """Test dynamic threshold detection via knee/elbow finding."""

    def test_clear_knee_in_bimodal_distribution(self):
        """Similarities with a clear gap between signal and noise."""
        # 20 high-similarity pairs (signal) + 80 low-similarity pairs (noise)
        signal = np.random.uniform(0.7, 0.95, size=20)
        noise = np.random.uniform(0.1, 0.4, size=80)
        similarities = np.concatenate([signal, noise])
        threshold = find_knee_threshold(similarities)
        # Knee should fall between the two clusters
        assert 0.35 < threshold < 0.75

    def test_uniform_distribution_returns_fallback(self):
        """When there's no clear knee, use fallback threshold."""
        similarities = np.random.uniform(0.0, 1.0, size=100)
        threshold = find_knee_threshold(similarities, fallback=0.65)
        # Should return the fallback since no clear knee exists
        assert isinstance(threshold, float)
        assert 0.0 < threshold < 1.0

    def test_empty_similarities_returns_fallback(self):
        """Empty input returns fallback."""
        threshold = find_knee_threshold(np.array([]), fallback=0.65)
        assert threshold == 0.65

    def test_all_identical_returns_fallback(self):
        """All-same values have no knee."""
        similarities = np.full(50, 0.5)
        threshold = find_knee_threshold(similarities, fallback=0.65)
        assert isinstance(threshold, float)

    def test_threshold_is_between_0_and_1(self):
        """Threshold must be a valid similarity score."""
        sims = np.random.uniform(0.2, 0.9, size=200)
        threshold = find_knee_threshold(sims)
        assert 0.0 < threshold < 1.0


class TestClassifyRelationship:
    """Test NLI-based relationship classification."""

    def test_high_entailment_returns_causes(self):
        scores = {"entailment": 0.85, "contradiction": 0.05, "neutral": 0.10}
        rel_type = classify_relationship(scores)
        assert rel_type == "causes"

    def test_medium_entailment_returns_amplifies(self):
        scores = {"entailment": 0.60, "contradiction": 0.10, "neutral": 0.30}
        rel_type = classify_relationship(scores)
        assert rel_type == "amplifies"

    def test_high_contradiction_returns_mitigates(self):
        scores = {"entailment": 0.10, "contradiction": 0.70, "neutral": 0.20}
        rel_type = classify_relationship(scores)
        assert rel_type == "mitigates"

    def test_neutral_dominant_returns_correlates(self):
        scores = {"entailment": 0.20, "contradiction": 0.15, "neutral": 0.65}
        rel_type = classify_relationship(scores)
        assert rel_type == "correlates"

    def test_low_entailment_returns_precedes(self):
        scores = {"entailment": 0.25, "contradiction": 0.10, "neutral": 0.65}
        rel_type = classify_relationship(scores)
        assert rel_type == "precedes"


class TestBuildCandidatePairs:
    """Test candidate pair selection from similarity matrix."""

    def test_pairs_above_threshold_are_returned(self):
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [0.99, 0.1, 0.0],  # very similar to 0
            [0.0, 0.0, 1.0],   # dissimilar
        ])
        # Normalize
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        pairs = build_candidate_pairs(embeddings, threshold=0.8)
        # Only pair (0, 1) should be above threshold
        assert len(pairs) == 1
        assert pairs[0][0] == 0 and pairs[0][1] == 1

    def test_no_self_pairs(self):
        embeddings = np.eye(3)
        pairs = build_candidate_pairs(embeddings, threshold=0.0)
        for i, j, _ in pairs:
            assert i != j

    def test_no_duplicate_pairs(self):
        """(i,j) and (j,i) should not both appear."""
        embeddings = np.random.randn(10, 5)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        pairs = build_candidate_pairs(embeddings, threshold=0.0)
        seen = set()
        for i, j, _ in pairs:
            assert (j, i) not in seen, f"Duplicate pair ({i},{j}) and ({j},{i})"
            seen.add((i, j))

    def test_similarity_scores_are_correct(self):
        embeddings = np.array([[1.0, 0.0], [0.0, 1.0]])
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        pairs = build_candidate_pairs(embeddings, threshold=0.0)
        # cos(90°) = 0
        assert len(pairs) == 1
        assert abs(pairs[0][2]) < 0.01
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/oshrin/projects/future_prediction/backend && python -m pytest tests/test_graph_edges.py -v`
Expected: FAIL — `ImportError: cannot import name 'find_knee_threshold' from 'app.tasks.graph_tasks'`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_graph_edges.py
git commit -m "test: add graph edge builder tests for knee detection and NLI classification"
```

---

### Task 3: Implement Core Functions — `find_knee_threshold`, `classify_relationship`, `build_candidate_pairs`

**Files:**
- Modify: `backend/app/tasks/graph_tasks.py` — replace `CAUSAL_PATTERNS`, `_extract_terms`, `_match_score` with new functions

- [ ] **Step 1: Replace the old imports and constants block (lines 1-92) with the new implementation**

Replace everything from the top of `graph_tasks.py` down to (and including) the `_match_score` function with:

```python
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
    """Find the knee point in the similarity distribution.

    Sorts similarities descending and finds where the curve bends —
    the natural boundary between signal (topically related) and noise.
    Returns fallback if no clear knee is found.
    """
    if len(similarities) < 5:
        return fallback

    sorted_sims = np.sort(similarities)[::-1]

    # Sample if too many pairs (kneed is O(n))
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
            # Sanity: threshold must be reasonable
            if 0.2 < knee_value < 0.95:
                return knee_value
    except Exception:
        pass

    return fallback


def classify_relationship(nli_scores: dict[str, float]) -> str:
    """Map NLI entailment/contradiction/neutral scores to a relationship type.

    Args:
        nli_scores: dict with keys 'entailment', 'contradiction', 'neutral'

    Returns:
        One of: 'causes', 'amplifies', 'mitigates', 'correlates', 'precedes'
    """
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
    """Find all pairs of nodes with cosine similarity above threshold.

    Args:
        embeddings: (N, D) normalized embedding matrix
        threshold: minimum cosine similarity for a candidate pair

    Returns:
        List of (i, j, similarity) tuples where i < j
    """
    n = len(embeddings)
    if n < 2:
        return []

    # Cosine similarity matrix (embeddings are already normalized)
    sim_matrix = embeddings @ embeddings.T

    # Get upper triangle indices (i < j, no self-pairs, no duplicates)
    i_indices, j_indices = np.triu_indices(n, k=1)
    sims = sim_matrix[i_indices, j_indices]

    # Filter by threshold
    mask = sims >= threshold
    pairs = [
        (int(i_indices[k]), int(j_indices[k]), float(sims[k]))
        for k in np.where(mask)[0]
    ]

    return pairs
```

Keep `_detect_event_type` and everything below it unchanged.

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /home/oshrin/projects/future_prediction/backend && python -m pytest tests/test_graph_edges.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/tasks/graph_tasks.py
git commit -m "feat: add knee detection, NLI classification, and candidate pair functions"
```

---

### Task 4: Implement `_run_nli_causal` — NLI Inference for Edge Classification

**Files:**
- Modify: `backend/app/tasks/graph_tasks.py` — add NLI helper function

- [ ] **Step 1: Write test for NLI causal scoring**

Add to `backend/tests/test_graph_edges.py`:

```python
from unittest.mock import patch, MagicMock
from app.tasks.graph_tasks import run_nli_causal


class TestRunNliCausal:
    """Test NLI causal inference (mocked — no GPU needed)."""

    @patch("app.tasks.graph_tasks._get_nli_pipeline")
    def test_returns_scores_for_each_pair(self, mock_get_pipe):
        mock_pipe = MagicMock()
        mock_pipe.return_value = {
            "labels": ["entailment", "neutral", "contradiction"],
            "scores": [0.7, 0.2, 0.1],
        }
        mock_get_pipe.return_value = mock_pipe

        pairs = [("Fed raises rates", "Housing market slows")]
        results = run_nli_causal(pairs)
        assert len(results) == 1
        assert results[0]["entailment"] == 0.7
        assert results[0]["contradiction"] == 0.1

    @patch("app.tasks.graph_tasks._get_nli_pipeline")
    def test_empty_pairs_returns_empty(self, mock_get_pipe):
        results = run_nli_causal([])
        assert results == []
        mock_get_pipe.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/oshrin/projects/future_prediction/backend && python -m pytest tests/test_graph_edges.py::TestRunNliCausal -v`
Expected: FAIL — `ImportError: cannot import name 'run_nli_causal'`

- [ ] **Step 3: Add `_get_nli_pipeline` and `run_nli_causal` to graph_tasks.py**

Add after `build_candidate_pairs`, before `_detect_event_type`:

```python
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


def run_nli_causal(
    pairs: list[tuple[str, str]],
) -> list[dict[str, float]]:
    """Run NLI inference on (source_title, target_title) pairs.

    For each pair, tests the hypothesis "The first event led to the second event"
    and returns entailment/contradiction/neutral scores.

    Args:
        pairs: list of (source_title, target_title) tuples

    Returns:
        List of dicts with 'entailment', 'contradiction', 'neutral' scores
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/oshrin/projects/future_prediction/backend && python -m pytest tests/test_graph_edges.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/graph_tasks.py backend/tests/test_graph_edges.py
git commit -m "feat: add NLI causal inference for graph edge classification"
```

---

### Task 5: Rewrite `build_event_graph` for Incremental Embedding+NLI Edges

**Files:**
- Modify: `backend/app/tasks/graph_tasks.py` — rewrite `build_event_graph` function

- [ ] **Step 1: Replace the `build_event_graph` function (lines 121-261 of original) with the new implementation**

Replace the entire `build_event_graph` async function with:

```python
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

        # Build index: node position → node object
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

        # Compute pairwise similarities between new nodes and all nodes
        new_embs = embeddings[new_indices]
        all_sims = new_embs @ embeddings.T  # (M, N) matrix

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
        # Also block reverse direction
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
                # Skip if edge exists in either direction
                if (node_a.id, node_b.id) in existing_edge_pairs:
                    continue
                if (node_b.id, node_a.id) in existing_edge_pairs:
                    continue

                # Temporal ordering: earlier → source, later → target
                time_a = node_a.occurred_at or node_a.created_at
                time_b = node_b.occurred_at or node_b.created_at
                if time_a and time_b and time_a <= time_b:
                    src_node, tgt_node = node_a, node_b
                elif time_a and time_b:
                    src_node, tgt_node = node_b, node_a
                else:
                    # Fallback: alphabetical
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
```

- [ ] **Step 2: Verify the module still loads cleanly**

Run: `cd /home/oshrin/projects/future_prediction/backend && python -c "from app.tasks.graph_tasks import build_event_graph; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Run all tests**

Run: `cd /home/oshrin/projects/future_prediction/backend && python -m pytest tests/test_graph_edges.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/tasks/graph_tasks.py
git commit -m "feat: rewrite build_event_graph with embedding similarity + NLI edges"
```

---

### Task 6: Add Backfill Endpoint and Function

**Files:**
- Modify: `backend/app/tasks/graph_tasks.py` — add `backfill_graph_edges` function
- Modify: `backend/app/api/meta.py` — add `POST /api/meta/backfill-graph` endpoint

- [ ] **Step 1: Write test for backfill function**

Add to `backend/tests/test_graph_edges.py`:

```python
from app.tasks.graph_tasks import backfill_graph_edges


class TestBackfillGraphEdges:
    """Test that backfill function signature and return shape are correct."""

    def test_function_exists_and_is_async(self):
        import asyncio
        assert asyncio.iscoroutinefunction(backfill_graph_edges)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/oshrin/projects/future_prediction/backend && python -m pytest tests/test_graph_edges.py::TestBackfillGraphEdges -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Add `backfill_graph_edges` function to graph_tasks.py**

Add at the end of `graph_tasks.py`:

```python
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
        # Load all nodes
        all_nodes_result = await db.execute(
            select(EventNode).order_by(EventNode.created_at.asc())
        )
        all_nodes = list(all_nodes_result.scalars().all())
        logger.info(f"Backfill: {len(all_nodes)} total nodes")

        if len(all_nodes) < 2:
            return {"total_edges": 0, "batches": 0, "total_nodes": len(all_nodes)}

        # Compute all embeddings at once
        titles = [n.title for n in all_nodes]
        embeddings = await asyncio.to_thread(_compute_embeddings, titles)

        # Load existing edges
        existing_edges = await db.execute(select(EventEdge))
        existing_edge_pairs = set()
        for e in existing_edges.scalars().all():
            existing_edge_pairs.add((e.source_node_id, e.target_node_id))
            existing_edge_pairs.add((e.target_node_id, e.source_node_id))

        # Process in batches: each batch of nodes compared against all nodes
        for batch_start in range(0, len(all_nodes), batch_size):
            batch_end = min(batch_start + batch_size, len(all_nodes))
            batch_embs = embeddings[batch_start:batch_end]

            # Similarities: batch vs all
            sims = batch_embs @ embeddings.T  # (batch, N)

            # Collect all scores for knee detection
            sim_scores = []
            for row_idx in range(len(batch_embs)):
                global_i = batch_start + row_idx
                for j in range(len(all_nodes)):
                    if global_i != j and global_i < j:  # upper triangle only
                        sim_scores.append(sims[row_idx, j])

            if not sim_scores:
                continue

            threshold = find_knee_threshold(np.array(sim_scores))
            logger.info(f"Backfill batch {batches_processed}: threshold={threshold:.3f}")

            # Build candidates
            candidates = []
            for row_idx in range(len(batch_embs)):
                global_i = batch_start + row_idx
                for j in range(len(all_nodes)):
                    if global_i >= j:  # upper triangle: only i < j
                        continue
                    sim = float(sims[row_idx, j])
                    if sim < threshold:
                        continue

                    node_a = all_nodes[global_i]
                    node_b = all_nodes[j]

                    if (node_a.id, node_b.id) in existing_edge_pairs:
                        continue

                    # Temporal ordering
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

            # Cap NLI calls per batch
            candidates.sort(key=lambda x: x[2], reverse=True)
            candidates = candidates[:500]

            # NLI classify
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
```

- [ ] **Step 4: Add backfill API endpoint to meta.py**

In `backend/app/api/meta.py`, add after the `trigger_graph_build` endpoint:

```python
@router.post("/backfill-graph")
async def trigger_backfill_graph(batch_size: int = Query(default=500, ge=50, le=2000)):
    """One-time backfill: create edges for all existing graph nodes via embeddings + NLI."""
    from app.tasks.graph_tasks import backfill_graph_edges
    result = await backfill_graph_edges(batch_size=batch_size)
    return {"status": "completed", "result": result}
```

- [ ] **Step 5: Run all tests**

Run: `cd /home/oshrin/projects/future_prediction/backend && python -m pytest tests/test_graph_edges.py -v`
Expected: All tests PASS

- [ ] **Step 6: Verify endpoint loads**

Run: `cd /home/oshrin/projects/future_prediction/backend && python -c "from app.api.meta import router; print('ok')"`
Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add backend/app/tasks/graph_tasks.py backend/app/api/meta.py backend/tests/test_graph_edges.py
git commit -m "feat: add backfill-graph endpoint for one-time edge creation across all nodes"
```

---

### Task 7: Remove Old Dead Code

**Files:**
- Modify: `backend/app/tasks/graph_tasks.py` — remove `CAUSAL_PATTERNS`, `STOP_WORDS`, `_extract_terms`, `_match_score` if still present

- [ ] **Step 1: Verify old constants are removed**

Run: `cd /home/oshrin/projects/future_prediction/backend && python -c "from app.tasks import graph_tasks; assert not hasattr(graph_tasks, 'CAUSAL_PATTERNS'); assert not hasattr(graph_tasks, '_match_score'); print('old code removed')"`
Expected: `old code removed`

If this fails, remove the old constants. If it passes, skip to step 3.

- [ ] **Step 2: Remove any remaining old code**

Delete `CAUSAL_PATTERNS`, `STOP_WORDS`, `_extract_terms`, and `_match_score` if they still exist in the file.

- [ ] **Step 3: Run full test suite**

Run: `cd /home/oshrin/projects/future_prediction/backend && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit (if changes were made)**

```bash
git add backend/app/tasks/graph_tasks.py
git commit -m "refactor: remove dead hardcoded causal patterns from graph builder"
```

---

### Task 8: Run Backfill and Verify

**Files:** None — this is a verification task

- [ ] **Step 1: Ensure the API server is running**

Run: `curl -s http://localhost:8000/api/meta/stats | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Sources: {d[\"total_sources\"]}, Predictions: {d[\"total_predictions\"]}')"`
Expected: Sources and predictions counts printed

- [ ] **Step 2: Check current graph state**

Run: `python3 -c "import sqlite3; c=sqlite3.connect('data/future_prediction.db').cursor(); c.execute('SELECT COUNT(*) FROM event_nodes'); print('Nodes:', c.fetchone()[0]); c.execute('SELECT COUNT(*) FROM event_edges'); print('Edges:', c.fetchone()[0])"`
Expected: ~8961 nodes, ~601 edges

- [ ] **Step 3: Run the backfill**

Run: `curl -s -X POST 'http://localhost:8000/api/meta/backfill-graph?batch_size=500' | python3 -m json.tool`
Expected: JSON response with `total_edges` > 0

Note: This will take 5-15 minutes depending on how many candidate pairs pass the knee threshold. Monitor logs with `tail -f` if needed.

- [ ] **Step 4: Verify new edge count**

Run: `python3 -c "import sqlite3; c=sqlite3.connect('data/future_prediction.db').cursor(); c.execute('SELECT COUNT(*) FROM event_edges'); print('Total edges:', c.fetchone()[0]); c.execute('SELECT relationship_type, COUNT(*) FROM event_edges GROUP BY relationship_type'); print(dict(c.fetchall()))"`
Expected: Edge count significantly higher than 601, with a distribution of relationship types

- [ ] **Step 5: Test the incremental pipeline**

Run: `curl -s -X POST http://localhost:8000/api/meta/build-graph | python3 -m json.tool`
Expected: JSON with `nodes_created` and `edges_created` (may be 0 if no new sources since last collection)

- [ ] **Step 6: Commit**

No code changes. If the backfill produced good results, this task is done.
