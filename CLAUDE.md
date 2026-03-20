# Future Prediction Platform

Multi-agent prediction platform that aggregates data from prediction markets, news, and other sources to forecast future events.

## Architecture
- **Backend**: Python 3.12 + FastAPI (in `backend/`)
- **Frontend**: Next.js 14 + TypeScript + Tailwind (in `frontend/`)
- **Database**: SQLite (async via SQLAlchemy + aiosqlite)
- **GPU**: RTX 2060 SUPER 8GB — sentiment, NLI, embeddings (3 models, ~830MB VRAM)
- **Intelligence Layer**: Claude Code scheduled tasks (all thinking/analysis)

### Indicator Intelligence Layer
- **Indicator Model** — stores time-series economic data from government/institutional sources (FRED, CBS Israel, World Bank); each row is one data point for one series
- **Insight Model** — structured four-layer analysis tied to a `UserInterest`; layers are `ground_truth`, `trend_analysis`, `prediction`, and `action_items`
- **UserInterest as Control Plane** — the `UserInterest` table drives both market collection and indicator collection via JSON fields: `indicators` (list of series to track), `market_filters` (keyword/category filters for prediction markets), `region` (geographic scope), and `enabled` (active flag)

## GPU Models (all lazy-loaded, stay in VRAM)
- `cardiffnlp/twitter-roberta-base-sentiment-latest` (~500MB) — sentiment analysis
- `all-MiniLM-L6-v2` (~80MB) — sentence embeddings for cross-source matching
- `cross-encoder/nli-distilroberta-base` (~250MB) — NLI evidence scoring

## Prediction Pipeline

The platform runs two parallel tracks that feed a unified intelligence layer:

```
Track 1 — Market/News:
  collect (4 sources) → sentiment (GPU) → match (GPU embeddings) → graph → predict (8 tools) → score

Track 2 — Indicators:
  collect-indicators (FRED / CBS_IL / WORLD_BANK) → Indicator table → generate-insights → Insight table

Intelligence layer (Claude Code):
  insight-context/{interest_id} → [Claude reasoning] → POST /api/insights/
```

### Data Sources (signal_type field)
- **Polymarket** — `market_probability` (real prediction market odds)
- **Manifold Markets** — `market_probability` (community prediction markets)
- **GDELT** — `news` (global news articles, no probability)
- **Reddit** — `engagement` (social posts, no probability)
- **FRED** — `indicator` (US economic indicators — requires `FRED_API_KEY` env var)
- **CBS_IL** — `indicator` (Israeli economic indicators — public API, no key needed)
- **WORLD_BANK** — `indicator` (global economic indicators — public API, no key needed)

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
- `POST /api/meta/collect-indicators` - Trigger indicator collection for all active interests
- `POST /api/meta/generate-insights` - Trigger insight generation (calls Claude Code reasoning)
- `GET /api/meta/insight-context/{interest_id}` - Full context bundle for Claude Code reasoning (indicators, recent news, market signals, prior insights)

Additional API routers:
- `GET /api/indicators/` - List available indicator series
- `GET /api/indicators/{series_id}/history` - Time-series data for a specific indicator
- `GET /api/insights/` - List insights (filterable by interest)
- `POST /api/insights/` - Create a new layered insight
- `GET /api/insights/{id}` - Retrieve a specific insight
- `PUT /api/insights/{id}` - Update an insight
- `DELETE /api/insights/{id}` - Delete an insight

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

# Seed default interests (creates UserInterest rows with indicator/market config)
cd backend && python -m app.seed_interests
```

## Project Structure
- `backend/app/models/` - SQLAlchemy models (Source, Prediction, PredictionScore, Agent, UserInterest, EventNode, EventEdge, Indicator, Insight)
- `backend/app/api/` - FastAPI routers (dashboard, meta, predictions, event_graph, interests, indicators, insights)
- `backend/app/agents/collector/` - Data collectors (Polymarket, Manifold, GDELT, Reddit, FRED, CBS_IL, WorldBank)
- `backend/app/agents/meta/` - Simplified meta-agents (DB operations only)
- `backend/app/tools/` - 8 prediction tools + evaluation framework (loss functions, comparator, experiments)
- `backend/app/tasks/` - Async tasks (collection, sentiment, embedding, prediction, scoring, graph, meta, indicators, insights)
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
- `UserInterest.indicators` is a JSON list of series IDs to collect; `UserInterest.market_filters` is a JSON object with keyword/category rules; `UserInterest.region` scopes geographic sources; `UserInterest.enabled` gates all collection for that interest
- `Insight` rows are keyed to a `UserInterest` and contain four JSON fields: `ground_truth`, `trend_analysis`, `prediction`, `action_items` — always written by Claude Code via the insights API
