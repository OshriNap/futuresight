# Future Prediction Platform

Multi-agent prediction platform that aggregates data from prediction markets, news, and other sources to forecast future events.

## Architecture
- **Backend**: Python 3.12 + FastAPI (in `backend/`)
- **Frontend**: Next.js 14 + TypeScript + Tailwind (in `frontend/`)
- **Database**: SQLite (async via SQLAlchemy + aiosqlite)
- **GPU**: RTX 2060 SUPER 8GB — sentiment, NLI, embeddings (3 models, ~830MB VRAM)
- **Intelligence Layer**: Claude Code scheduled tasks (all thinking/analysis)

## GPU Models (all lazy-loaded, stay in VRAM)
- `cardiffnlp/twitter-roberta-base-sentiment-latest` (~500MB) — sentiment analysis
- `all-MiniLM-L6-v2` (~80MB) — sentence embeddings for cross-source matching
- `cross-encoder/nli-distilroberta-base` (~250MB) — NLI evidence scoring

## Prediction Pipeline
```
collect (4 sources) → sentiment (GPU) → match (GPU embeddings) → graph → predict (8 tools) → score
```

### Data Sources (signal_type field)
- **Polymarket** — `market_probability` (real prediction market odds)
- **Manifold Markets** — `market_probability` (community prediction markets)
- **GDELT** — `news` (global news articles, no probability)
- **Reddit** — `engagement` (social posts, no probability)

### 8 Prediction Tools (ToolRegistry)
- `market_consensus` — market probability baseline
- `multi_market_ensemble` — cross-platform market agreement
- `trend_extrapolation` / `advanced_extrapolation` — price history trends
- `llm_reasoning` — heuristic reasoning with sentiment signal
- `base_rate_adjustment` — category base rates
- `nli_evidence` — GPU NLI model scores news vs prediction (Phase 3)
- `graph_context` — event causality graph signal (Phase 3)

Ensemble: log-linear pooling with extremization (d=1.2)

### Scoring & Feedback Loop
- `scoring_tasks.py` resolves markets via Polymarket/Manifold APIs
- Computes Brier score + absolute error → PredictionScore table
- `build_performance_data()` feeds per-tool scores back to ToolRegistry
- Tools with 5+ scored predictions get performance-weighted selection

## Intelligence Architecture
**No Anthropic API calls.** All LLM reasoning is done by Claude Code scheduled tasks:
- `meta-source-evaluator` - Evaluates data source reliability (daily 6 AM)
- `meta-strategy-optimizer` - Analyzes prediction accuracy (daily 6:15 AM)
- `meta-feature-ideator` - Brainstorms improvements (Mon & Thu 7 AM)
- `data-collection-orchestrator` - Runs collectors and monitors freshness (every 4 hours)

Scheduled tasks interact with the system via REST API (`http://localhost:8000/api/meta/`):
- `GET /api/meta/stats` - System-wide statistics
- `POST /api/meta/collect/{name}` - Trigger collection (polymarket, manifold, gdelt, reddit, all)
- `POST /api/meta/run-pipeline` - Full pipeline: collect → match → graph → predict → score
- `POST /api/meta/match-sources` - GPU embedding matching
- `POST /api/meta/analyze-sentiment` - GPU sentiment analysis
- `POST /api/meta/score-predictions` - Resolve markets and score
- `POST /api/meta/generate-predictions` - Generate/update predictions
- `POST /api/meta/build-graph` - Build event causality graph

## Development
```bash
# No external services needed - SQLite is file-based
cd backend && pip install -e ".[gpu]" && cd ..
cd frontend && npm install && cd ..
./dev.sh                 # Start API (0.0.0.0:8000) + frontend (:3000)
./dev.sh api             # Or start individually
# Dashboard: http://<server-ip>:8000/  (HTML single-page app)
# API docs: http://<server-ip>:8000/docs
# Next.js: http://localhost:3000
```

## Project Structure
- `backend/app/models/` - SQLAlchemy models (Source, Prediction, PredictionScore, Agent, UserInterest, EventNode, EventEdge)
- `backend/app/api/` - FastAPI routers (dashboard, meta, predictions, event_graph, interests)
- `backend/app/agents/collector/` - Data collectors (Polymarket, Manifold, GDELT, Reddit)
- `backend/app/agents/meta/` - Simplified meta-agents (DB operations only)
- `backend/app/tools/` - 8 prediction tools + evaluation framework (loss functions, comparator, experiments)
- `backend/app/tasks/` - Async tasks (collection, sentiment, embedding, prediction, scoring, graph, meta)
- `frontend/src/app/` - Next.js pages (dashboard, predictions, accuracy, agents, graph, interests)
- `.claude/skills/` - Claude Code skills (analyze-sentiment)

## Key Patterns
- All DB operations are async (SQLAlchemy async sessions)
- Collectors inherit from `BaseCollector` in `agents/collector/base.py`
- Collectors pull keywords from `UserInterest` table for interest-aware search
- `Source.signal_type` distinguishes market_probability from news/engagement (never mix)
- GPU models lazy-load and stay in VRAM across calls
- Sentiment runs automatically after each collection
- JSON mutation tracking: use `flag_modified()` when updating `raw_data` dicts
- Tables are auto-created on startup (no Alembic needed for SQLite dev)
- `Source` has unique constraint on (platform, external_id)
