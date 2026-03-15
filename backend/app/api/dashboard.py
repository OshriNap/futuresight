import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
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


class SourceResponse(BaseModel):
    id: uuid.UUID
    platform: str
    external_id: str
    title: str
    description: str | None
    category: str | None
    current_market_probability: float | None
    resolution_date: datetime | None
    raw_data: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SentimentStats(BaseModel):
    total_scored: int
    total_sources: int
    coverage_pct: float
    avg_sentiment: float | None
    by_label: dict[str, int]
    by_platform: dict[str, dict[str, int]]


@router.get("/sentiment", response_model=SentimentStats)
async def get_sentiment_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(Source.id)))).scalar() or 0
    result = await db.execute(select(Source).limit(5000))
    sources = result.scalars().all()

    scored = 0
    labels: dict[str, int] = {}
    scores: list[float] = []
    by_platform: dict[str, dict[str, int]] = {}

    for s in sources:
        raw = s.raw_data or {}
        plat = s.platform
        if plat not in by_platform:
            by_platform[plat] = {"total": 0, "scored": 0}
        by_platform[plat]["total"] += 1

        if "sentiment" in raw:
            scored += 1
            by_platform[plat]["scored"] += 1
            scores.append(raw["sentiment"])
            label = raw.get("sentiment_label", "neutral")
            labels[label] = labels.get(label, 0) + 1

    return SentimentStats(
        total_scored=scored,
        total_sources=total,
        coverage_pct=round(scored / max(total, 1) * 100, 1),
        avg_sentiment=round(sum(scores) / len(scores), 3) if scores else None,
        by_label=labels,
        by_platform=by_platform,
    )


class AccuracyStats(BaseModel):
    overall_brier: float | None
    total_scored: int
    total_predictions: int
    by_category: list[dict]
    by_tool: list[dict]
    calibration_curve: list[dict]


@router.get("/accuracy", response_model=AccuracyStats)
async def get_accuracy_stats(db: AsyncSession = Depends(get_db)):
    """Accuracy stats from scored predictions for the accuracy page."""
    from collections import defaultdict

    from app.models.prediction import Prediction, PredictionScore

    total_preds = (await db.execute(select(func.count(Prediction.id)))).scalar() or 0

    # Get all scored predictions
    result = await db.execute(
        select(Prediction, PredictionScore)
        .join(PredictionScore, PredictionScore.prediction_id == Prediction.id)
    )
    rows = result.all()

    if not rows:
        return AccuracyStats(
            overall_brier=None, total_scored=0, total_predictions=total_preds,
            by_category=[], by_tool=[], calibration_curve=[],
        )

    # Overall
    brier_scores = [score.brier_score for _, score in rows]
    overall_brier = sum(brier_scores) / len(brier_scores)

    # By category
    cat_data: dict[str, list[float]] = defaultdict(list)
    for pred, score in rows:
        ds = pred.data_signals or {}
        cat = ds.get("category") or "general"
        cat_data[cat].append(score.brier_score)

    by_category = [
        {
            "category": cat,
            "brier": round(sum(scores) / len(scores), 4),
            "count": len(scores),
            "accuracy": round(sum(1 for s in scores if s < 0.25) / len(scores) * 100),
        }
        for cat, scores in sorted(cat_data.items())
    ]

    # By tool
    tool_data: dict[str, list[float]] = defaultdict(list)
    for pred, score in rows:
        ds = pred.data_signals or {}
        for tool in ds.get("tools_used", []):
            tool_data[tool].append(score.brier_score)

    by_tool = [
        {
            "tool": tool,
            "brier": round(sum(scores) / len(scores), 4),
            "count": len(scores),
        }
        for tool, scores in sorted(tool_data.items())
    ]

    # Calibration curve (10 bins)
    calibration = []
    pred_actual_pairs = []
    for pred, score in rows:
        source = await db.get(Source, pred.source_id)
        if source and source.actual_outcome:
            actual = 1.0 if source.actual_outcome in ("yes",) else 0.0
            pred_actual_pairs.append((pred.confidence, actual))

    if pred_actual_pairs:
        n_bins = 10
        bins: dict[int, list[tuple[float, float]]] = defaultdict(list)
        for predicted, actual in pred_actual_pairs:
            bin_idx = min(int(predicted * n_bins), n_bins - 1)
            bins[bin_idx].append((predicted, actual))

        for i in range(n_bins):
            if i in bins:
                preds_in_bin = bins[i]
                avg_pred = sum(p for p, _ in preds_in_bin) / len(preds_in_bin)
                avg_actual = sum(a for _, a in preds_in_bin) / len(preds_in_bin)
                calibration.append({
                    "bin_center": round((i + 0.5) / n_bins, 2),
                    "predicted_avg": round(avg_pred, 3),
                    "actual_rate": round(avg_actual, 3),
                    "count": len(preds_in_bin),
                })

    return AccuracyStats(
        overall_brier=round(overall_brier, 4),
        total_scored=len(rows),
        total_predictions=total_preds,
        by_category=by_category,
        by_tool=by_tool,
        calibration_curve=calibration,
    )


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(
    platform: str | None = None,
    has_probability: bool = False,
    search: str | None = None,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Source).order_by(Source.updated_at.desc()).limit(limit)
    if platform:
        query = query.where(Source.platform == platform)
    if has_probability:
        query = query.where(Source.current_market_probability.isnot(None))
    if search:
        query = query.where(Source.title.ilike(f"%{search}%"))
    result = await db.execute(query)
    return result.scalars().all()
