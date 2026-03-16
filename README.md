# FutureSight

A multi-agent prediction platform that aggregates signals from prediction markets, global news, and social media to forecast future events. Uses local GPU inference for sentiment analysis, semantic matching, and natural language inference — with all strategic reasoning handled by Claude Code scheduled tasks at zero API cost.

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Data Collection                              │
│  Polymarket ─┐                                                      │
│  Manifold   ─┼─→ Sentiment (GPU) ─→ Embedding Match (GPU) ─┐       │
│  GDELT News ─┤                                               │      │
│  Reddit     ─┘                                               ▼      │
│                                                     Event Graph     │
│                                                          │          │
│                              ┌────────────────────────────┘          │
│                              ▼                                      │
│                     8 Prediction Tools                              │
│            (market consensus, NLI evidence,                         │
│             trend extrapolation, graph context,                     │
│             base rates, sentiment divergence, ...)                  │
│                              │                                      │
│                              ▼                                      │
│                  Log-Linear Ensemble (d=1.2)                        │
│                              │                                      │
│                              ▼                                      │
│               Predictions + Brier Score Feedback                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Features

- **4 Data Sources** — Polymarket, Manifold Markets, GDELT global news, Reddit
- **GPU-Accelerated Analysis** — Sentiment classification, semantic embeddings, NLI evidence scoring (~830MB VRAM)
- **8 Prediction Tools** — Market consensus, multi-market ensemble, trend extrapolation, LLM reasoning, base rate adjustment, NLI evidence, graph context, and more
- **Event Causality Graph** — Tracks causal relationships between events (causes, amplifies, correlates, mitigates)
- **Self-Improving** — Brier score feedback loop adjusts tool weights based on historical accuracy
- **Interest-Aware** — User-defined interests drive targeted data collection
- **Zero API Cost** — All LLM reasoning via Claude Code scheduled tasks; GPU models run locally

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 (async) |
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS, Recharts |
| Database | SQLite (via aiosqlite) |
| GPU | PyTorch + Transformers (RTX 2060 SUPER 8GB) |
| Intelligence | Claude Code scheduled tasks |

## GPU Models

Three models are lazy-loaded and stay resident in VRAM:

| Model | Size | Purpose |
|-------|------|---------|
| `cardiffnlp/twitter-roberta-base-sentiment-latest` | ~500MB | Sentiment analysis on source titles |
| `all-MiniLM-L6-v2` | ~80MB | Sentence embeddings for cross-source matching |
| `cross-encoder/nli-distilroberta-base` | ~250MB | NLI evidence scoring (entail/contradict/neutral) |

## Data Sources

### Polymarket
Real prediction market odds from the Gamma API. Collects top markets by volume plus user-interest keyword searches. Signal type: `market_probability`.

### Manifold Markets
Community prediction markets. Filters for binary markets across search terms (prediction, technology, geopolitics, economy) plus user interests. Signal type: `market_probability`.

### GDELT
Global news articles via the GDELT DOC API. 50 articles per keyword with tone extraction and theme-based category detection. Signal type: `news`.

### Reddit
Hot posts from r/worldnews, r/technology, r/science, r/economics plus interest-based keyword search via Reddit's JSON API. Signal type: `engagement`.

## Prediction Pipeline

### 1. Collection
All four collectors run in parallel, pulling ~750+ sources per cycle. Each collector also queries the `UserInterest` table for personalized keyword searches.

### 2. Sentiment Analysis
The RoBERTa sentiment model classifies source titles as positive/negative/neutral with confidence scores. Processes in batches of 32, up to 500 sources per run.

### 3. Semantic Matching
The MiniLM embedding model computes cosine similarity between market questions and news/social content. Sources with similarity ≥ 0.45 are linked, connecting market predictions to their supporting evidence.

### 4. Event Graph
High-signal sources become nodes in a causality graph. Edges are created via 12+ causal patterns with relationship types: causes, amplifies, correlates, precedes, mitigates.

### 5. Prediction Generation
The tool registry selects the best tools for each prediction based on category and historical performance:

| Tool | Type | Description |
|------|------|-------------|
| `market_consensus` | Heuristic | Market probability baseline, confidence scaled by volume |
| `multi_market_ensemble` | Ensemble | Weighted average across platforms by source reliability |
| `trend_extrapolation` | Statistical | Linear regression on probability history (requires 3+ data points) |
| `advanced_extrapolation` | Statistical | Advanced trend analysis with moving averages |
| `llm_reasoning` | Heuristic | Signal-weighted reasoning with sentiment (LLM thinking via Claude Code) |
| `base_rate_adjustment` | Statistical | Anchors toward category base rates (e.g., politics 42%, tech 35%) |
| `nli_evidence` | ML | GPU NLI model scores up to 15 matched headlines per prediction |
| `graph_context` | Heuristic | Causality graph signals with relationship multipliers |

Tools are combined via **log-linear pooling with extremization** (d=1.2), producing a final probability estimate.

### 6. Scoring & Feedback
Markets are checked for resolution via Polymarket/Manifold APIs. Resolved predictions are scored with Brier score and absolute error. Tools with 5+ scored predictions get performance-weighted selection in future runs.

## Scheduled Intelligence

All strategic analysis runs via Claude Code scheduled tasks — no Anthropic API calls needed:

| Agent | Schedule | Purpose |
|-------|----------|---------|
| `data-collection-orchestrator` | Every 4 hours | Runs collectors, monitors data freshness |
| `meta-source-evaluator` | Daily 6:00 AM | Evaluates platform reliability scores |
| `meta-strategy-optimizer` | Daily 6:15 AM | Analyzes prediction accuracy and calibration |
| `meta-feature-ideator` | Mon & Thu 7:00 AM | Brainstorms system improvements |

These tasks interact with the system via the REST API at `http://localhost:8000/api/meta/`.

## API Endpoints

### Dashboard & Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dashboard/stats` | System-wide statistics |
| `GET` | `/api/dashboard/sentiment` | Sentiment analysis overview |
| `GET` | `/api/dashboard/accuracy` | Accuracy metrics and calibration |
| `GET` | `/api/dashboard/sources` | Browse sources with filters |

### Predictions
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/predictions` | List predictions (filter by horizon, search) |
| `GET` | `/api/predictions/{id}` | Single prediction details |
| `GET` | `/api/predictions/{id}/history` | Price history for sparklines |
| `POST` | `/api/predictions` | Create a prediction |

### Event Graph
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/graph` | Full graph (filter by category, event type, min strength) |
| `GET` | `/api/graph/node/{id}/connections` | Node with N-hop neighbors |

### Meta / Pipeline Control
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/meta/run-pipeline` | Full pipeline: collect → match → graph → predict → score |
| `POST` | `/api/meta/collect/{name}` | Trigger specific collector (polymarket, manifold, gdelt, reddit, all) |
| `POST` | `/api/meta/generate-predictions` | Run prediction generation |
| `POST` | `/api/meta/match-sources` | GPU embedding matching |
| `POST` | `/api/meta/analyze-sentiment` | GPU sentiment analysis |
| `POST` | `/api/meta/build-graph` | Build event causality graph |
| `POST` | `/api/meta/score-predictions` | Resolve markets and score |
| `POST` | `/api/meta/backtest` | Backtest against resolved Manifold markets |
| `GET` | `/api/meta/stats` | System statistics |

Interactive API docs available at `/docs` (Swagger UI).

## Database Schema

13 tables managed by SQLAlchemy with auto-creation on startup (no migrations needed):

**Core:** `sources`, `predictions`, `prediction_scores`, `price_history`, `agents`

**Graph:** `event_nodes`, `event_edges`

**User:** `user_interests`

**Meta:** `scratchpads`, `source_reliability`, `prediction_methods`, `feature_importance`, `meta_agent_runs`

Key constraints:
- `Source` has a unique constraint on `(platform, external_id)` for idempotent collection
- `Source.signal_type` distinguishes `market_probability` from `news`/`engagement` — never mixed
- JSON fields use `flag_modified()` for SQLite mutation tracking

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 18+
- NVIDIA GPU with 1GB+ VRAM (optional, for local inference)

### Installation

```bash
# Clone
git clone https://github.com/OshriNap/futuresight.git
cd futuresight

# Backend
cd backend
pip install -e ".[gpu]"    # With GPU support
# pip install -e .          # CPU-only (slower inference)
cd ..

# Frontend
cd frontend
npm install
cd ..
```

### Running

```bash
./dev.sh                   # Start API (:8000) + Frontend (:3000)
./dev.sh api               # API only
./dev.sh frontend          # Frontend only
```

- **Dashboard:** `http://localhost:8000/` (HTML single-page app)
- **API Docs:** `http://localhost:8000/docs` (Swagger)
- **Next.js Frontend:** `http://localhost:3000/`

### Running the Pipeline

```bash
# Full pipeline (collect → sentiment → match → graph → predict → score)
curl -X POST http://localhost:8000/api/meta/run-pipeline

# Or run individual steps
curl -X POST http://localhost:8000/api/meta/collect/all
curl -X POST http://localhost:8000/api/meta/analyze-sentiment
curl -X POST http://localhost:8000/api/meta/match-sources
curl -X POST http://localhost:8000/api/meta/build-graph
curl -X POST http://localhost:8000/api/meta/generate-predictions
curl -X POST http://localhost:8000/api/meta/score-predictions
```

## Project Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI app + startup
│   ├── models/                  # SQLAlchemy models (13 tables)
│   ├── api/                     # Routers (dashboard, meta, predictions, graph, interests)
│   ├── agents/
│   │   ├── collector/           # Polymarket, Manifold, GDELT, Reddit collectors
│   │   └── meta/                # Meta-agents (source evaluator, strategy optimizer, method researcher)
│   ├── tools/                   # 8 prediction tools + evaluation framework
│   └── tasks/                   # Async tasks (collection, sentiment, embedding, prediction, scoring, graph)
frontend/
├── src/app/                     # Next.js pages (dashboard, predictions, accuracy, agents, graph, interests)
```

## Architecture Decisions

- **No Anthropic API calls** — All LLM reasoning delegated to Claude Code scheduled tasks, making intelligence essentially free
- **Local GPU inference** — Three lean models (~830MB total) provide real-time NLP without external API latency or cost
- **SQLite** — Zero-config database suitable for single-server deployment; async via aiosqlite
- **Log-linear ensemble** — Combines tool outputs multiplicatively with extremization, reducing overconfidence from any single signal
- **Performance feedback loop** — Tools earn their weight through actual Brier score performance, not static configuration

## License

MIT
