# Graph Edge Builder — Embedding + NLI Causal Edge Discovery

## Problem

The event causality graph has 8,961 nodes but only 601 edges (98% isolated). The current edge builder uses 12 hardcoded keyword patterns with exact substring matching — no semantic understanding. Recent pipeline runs create 0 new edges. The `graph_context` prediction tool (Brier 0.150) is effectively non-functional for most predictions.

## Solution

Replace hardcoded pattern matching with embedding similarity (MiniLM) for candidate discovery and NLI scoring (cross-encoder) for causal classification. Use dynamic thresholding via knee detection instead of a fixed similarity cutoff. Enforce temporal ordering for edge directionality.

## Algorithm

### Step 1: Compute Embeddings

Encode all node titles using `all-MiniLM-L6-v2` (already loaded in VRAM, ~80MB). Embeddings are 384-dimensional, L2-normalized.

### Step 2: Cosine Similarity Matrix

For a batch of N nodes, compute pairwise cosine similarity. For backfill batches of 500 nodes, this is a 500×500 matrix — trivial on GPU.

For incremental runs, compute similarity between new nodes (M) and all existing nodes (N), producing an M×N matrix.

### Step 3: Dynamic Threshold via Knee Detection

Sort all pairwise similarity scores descending. Apply the kneedle algorithm to find the "elbow" — the point where similarity drops off sharply from signal to noise. Use this as the candidate threshold.

- Use the `kneed` Python library (KneeLocator with curve="convex", direction="decreasing")
- Input: sorted similarity scores (sampled if >100k pairs for performance)
- Output: similarity threshold that separates topically related pairs from noise
- Fallback: if knee detection fails (e.g., uniform distribution), use 0.65 as default

### Step 4: Temporal Ordering

For each candidate pair (A, B) above threshold:
- Use `occurred_at` timestamp (falls back to `created_at`)
- Earlier event becomes `source_node`, later event becomes `target_node`
- If timestamps are identical, use alphabetical ordering by title (deterministic)

### Step 5: NLI Classification

Single NLI call per candidate pair using `cross-encoder/nli-distilroberta-base` (already loaded, ~250MB):

- Input: `"{source_title}" → "{target_title}"`
- Hypothesis: `"The first event led to the second event"`
- Output: entailment, contradiction, neutral scores (sum to 1.0)

Map to relationship types:
| NLI Result | Condition | Relationship Type |
|------------|-----------|-------------------|
| Entailment > 0.8 | — | `causes` |
| Entailment 0.5–0.8 | — | `amplifies` |
| Contradiction > 0.5 | — | `mitigates` |
| Neutral dominant | Above similarity threshold | `correlates` |
| Entailment < 0.3 | Temporal gap < 24h | `precedes` |

### Step 6: Edge Creation

- `strength` = entailment_score × cosine_similarity
- `reasoning` = auto-generated: `"Semantic similarity: {sim:.2f}, NLI entailment: {ent:.2f}"`
- `detected_by` = `"agent"`
- Drop edges with strength < 0.1
- Skip if edge already exists between the same two nodes

## Execution Modes

### Backfill (one-time)

Process all ~9k existing nodes in batches of 500:
1. Load all node titles + timestamps
2. For each batch of 500, compute embeddings and pairwise similarity
3. Also compute cross-batch similarity (batch vs all previously processed nodes)
4. Apply knee threshold, NLI classify, create edges
5. Exposed as API endpoint: `POST /api/meta/backfill-graph`

### Incremental (pipeline)

Replaces current `build_event_graph` in the 4-hour pipeline cycle:
1. Query nodes created since last graph build (track via timestamp or marker)
2. Compute embeddings for new nodes only
3. Compare new nodes against all existing nodes (M×N similarity)
4. Apply knee threshold from the new similarities, NLI classify, create edges
5. If no new nodes, skip entirely

## Performance Estimates

- MiniLM embedding: ~0.5ms per title (GPU batch)
- Cosine similarity matrix (500×500): <1ms on GPU
- NLI inference: ~5ms per pair (GPU)
- Backfill 9k nodes: ~18 batches × (embedding + knee + NLI for candidates) — estimate 5-15 minutes total
- Incremental run with ~60 new nodes: <30 seconds

## Dependencies

- `kneed` Python package (pip install kneed) — for knee detection
- Both GPU models already loaded and in VRAM
- No schema changes needed — uses existing EventNode/EventEdge models

## Files to Change

| File | Change |
|------|--------|
| `backend/app/tasks/graph_tasks.py` | Replace `CAUSAL_PATTERNS` + substring matching with embedding+NLI algorithm |
| `backend/app/api/meta.py` | Add `POST /api/meta/backfill-graph` endpoint |
| `backend/requirements.txt` or `pyproject.toml` | Add `kneed` dependency |

## Out of Scope

- Changing the `graph_context` prediction tool logic — it already traverses edges correctly
- Changing the EventNode/EventEdge schema
- Storing embeddings persistently (computed on-the-fly per batch, cheap enough)
