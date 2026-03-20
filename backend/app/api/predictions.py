import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.prediction import Prediction

router = APIRouter()


class PredictionCreate(BaseModel):
    source_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    prediction_text: str
    predicted_outcome: str | None = None
    confidence: float
    reasoning: str | None = None
    time_horizon: str = "medium"
    data_signals: dict | None = None


class PredictionResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID | None
    agent_id: uuid.UUID | None
    prediction_text: str
    predicted_outcome: str | None
    confidence: float
    reasoning: str | None
    time_horizon: str
    data_signals: dict | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[PredictionResponse])
async def list_predictions(
    time_horizon: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Prediction).order_by(Prediction.created_at.desc()).offset(offset).limit(limit)
    if time_horizon:
        query = query.where(Prediction.time_horizon == time_horizon)
    if search:
        query = query.where(Prediction.prediction_text.ilike(f"%{search}%"))
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{prediction_id}", response_model=PredictionResponse)
async def get_prediction(prediction_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prediction).where(Prediction.id == prediction_id))
    prediction = result.scalar_one_or_none()
    if not prediction:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Prediction not found")
    return prediction


@router.get("/{prediction_id}/history")
async def get_prediction_history(prediction_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get price history for a prediction's linked source (for sparklines)."""
    from app.models.price_history import PriceSnapshot

    result = await db.execute(select(Prediction).where(Prediction.id == prediction_id))
    prediction = result.scalar_one_or_none()
    if not prediction or not prediction.source_id:
        return []

    history = await db.execute(
        select(PriceSnapshot)
        .where(PriceSnapshot.source_id == prediction.source_id)
        .order_by(PriceSnapshot.recorded_at.asc())
        .limit(100)
    )
    return [
        {"timestamp": s.recorded_at.isoformat(), "probability": s.probability}
        for s in history.scalars().all()
    ]


@router.get("/{prediction_id}/counterfactual")
async def get_counterfactual(prediction_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Counterfactual analysis: what if we dropped or reweighted each tool?

    Uses stored tool_outputs from data_signals to recompute the ensemble
    with each tool removed, showing each tool's marginal contribution.
    """
    import math

    result = await db.execute(select(Prediction).where(Prediction.id == prediction_id))
    prediction = result.scalar_one_or_none()
    if not prediction:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Prediction not found")

    ds = prediction.data_signals or {}
    tool_outputs = ds.get("tool_outputs", {})
    ensemble_prob = ds.get("ensemble_probability", prediction.confidence)

    if not tool_outputs:
        return {
            "prediction_id": str(prediction_id),
            "ensemble_probability": ensemble_prob,
            "counterfactuals": [],
            "message": "No per-tool outputs stored (prediction made before counterfactual tracking)"
        }

    # Recompute ensemble without each tool (log-linear pooling)
    def log_linear_ensemble(tools: dict) -> float:
        if not tools:
            return 0.5
        total_w = sum(t["weight"] for t in tools.values())
        if total_w == 0:
            return 0.5
        log_odds = 0.0
        for t in tools.values():
            p = max(0.01, min(0.99, t["probability"]))
            log_odds += (t["weight"] / total_w) * math.log(p / (1 - p))
        return max(0.02, min(0.98, 1.0 / (1.0 + math.exp(-log_odds))))

    full_prob = log_linear_ensemble(tool_outputs)

    counterfactuals = []
    for tool_name, tool_data in tool_outputs.items():
        # Without this tool
        without = {k: v for k, v in tool_outputs.items() if k != tool_name}
        without_prob = log_linear_ensemble(without)
        shift = ensemble_prob - without_prob

        # With only this tool
        solo_prob = tool_data["probability"]

        counterfactuals.append({
            "tool": tool_name,
            "tool_probability": tool_data["probability"],
            "tool_confidence": tool_data["confidence"],
            "tool_weight": tool_data["weight"],
            "without_tool": round(without_prob, 4),
            "shift": round(shift, 4),  # positive = tool pushes probability up
            "direction": "pushes up" if shift > 0.01 else "pushes down" if shift < -0.01 else "minimal impact",
            "signals_used": tool_data.get("signals_used", []),
        })

    # Sort by absolute impact
    counterfactuals.sort(key=lambda x: abs(x["shift"]), reverse=True)

    return {
        "prediction_id": str(prediction_id),
        "prediction_text": prediction.prediction_text,
        "ensemble_probability": ensemble_prob,
        "recomputed_probability": round(full_prob, 4),
        "counterfactuals": counterfactuals,
    }


@router.post("/", response_model=PredictionResponse, status_code=201)
async def create_prediction(data: PredictionCreate, db: AsyncSession = Depends(get_db)):
    prediction = Prediction(**data.model_dump())
    db.add(prediction)
    await db.commit()
    await db.refresh(prediction)
    return prediction
