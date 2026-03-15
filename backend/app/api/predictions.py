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


@router.post("/", response_model=PredictionResponse, status_code=201)
async def create_prediction(data: PredictionCreate, db: AsyncSession = Depends(get_db)):
    prediction = Prediction(**data.model_dump())
    db.add(prediction)
    await db.commit()
    await db.refresh(prediction)
    return prediction
