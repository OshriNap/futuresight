from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent
from app.models.event_graph import EventEdge, EventNode
from app.models.prediction import Prediction, PredictionScore
from app.models.source import Source

router = APIRouter()


class DashboardStats(BaseModel):
    total_predictions: int
    total_sources: int
    total_agents: int
    avg_brier_score: float | None
    total_event_nodes: int
    total_event_edges: int
    predictions_by_horizon: dict[str, int]


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    pred_count = (await db.execute(select(func.count(Prediction.id)))).scalar() or 0
    source_count = (await db.execute(select(func.count(Source.id)))).scalar() or 0
    agent_count = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
    avg_brier = (await db.execute(select(func.avg(PredictionScore.brier_score)))).scalar()
    node_count = (await db.execute(select(func.count(EventNode.id)))).scalar() or 0
    edge_count = (await db.execute(select(func.count(EventEdge.id)))).scalar() or 0

    # Predictions by time horizon
    horizon_query = select(Prediction.time_horizon, func.count(Prediction.id)).group_by(Prediction.time_horizon)
    horizon_result = await db.execute(horizon_query)
    predictions_by_horizon = {row[0]: row[1] for row in horizon_result.all()}

    return DashboardStats(
        total_predictions=pred_count,
        total_sources=source_count,
        total_agents=agent_count,
        avg_brier_score=round(avg_brier, 4) if avg_brier else None,
        total_event_nodes=node_count,
        total_event_edges=edge_count,
        predictions_by_horizon=predictions_by_horizon,
    )
