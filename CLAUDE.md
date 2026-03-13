# Future Prediction Platform

Multi-agent prediction platform that aggregates data from prediction markets, news, and other sources to forecast future events.

## Architecture
- **Backend**: Python 3.12 + FastAPI (in `backend/`)
- **Frontend**: Next.js 14 + TypeScript + Tailwind (in `frontend/`)
- **Database**: PostgreSQL 16 (async via SQLAlchemy + asyncpg)
- **Task Queue**: Celery + Redis
- **Infrastructure**: Docker Compose

## Development
```bash
docker compose up        # Start all services
# API: http://localhost:8000/docs
# Dashboard: http://localhost:3000
```

## Project Structure
- `backend/app/models/` - SQLAlchemy models (Source, Prediction, Agent, UserInterest, EventNode, EventEdge)
- `backend/app/api/` - FastAPI routers
- `backend/app/agents/` - AI agents (collector, analyst, predictor, graph_builder)
- `backend/app/tasks/` - Celery scheduled tasks
- `frontend/src/app/` - Next.js pages (dashboard, predictions, accuracy, agents, graph, interests)

## Key Patterns
- All DB operations are async (SQLAlchemy async sessions)
- Collectors inherit from `BaseCollector` in `agents/collector/base.py`
- Celery tasks use `run_async()` helper for async code
- API responses use Pydantic models with `from_attributes=True`
