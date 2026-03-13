from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agents, dashboard, evaluation, event_graph, interests, meta, predictions, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Future Prediction Platform",
    description="Multi-agent prediction platform with event causality graph",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(interests.router, prefix="/api/interests", tags=["interests"])
app.include_router(event_graph.router, prefix="/api/graph", tags=["event-graph"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(meta.router, prefix="/api/meta", tags=["meta-agents"])
app.include_router(evaluation.router, prefix="/api/evaluation", tags=["evaluation"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
