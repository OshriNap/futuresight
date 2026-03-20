import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.insight import Insight

router = APIRouter()


class InsightCreate(BaseModel):
    domain: str
    title: str
    ground_truth: str
    trend_analysis: str
    prediction: str
    action_items: list[str] | None = None
    confidence: str = "medium"
    sources: dict | None = None


class InsightResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    domain: str
    title: str
    ground_truth: str
    trend_analysis: str
    prediction: str
    action_items: list[str] | None
    confidence: str
    sources: dict | None
    stale: bool

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[InsightResponse])
async def list_insights(
    domain: str | None = Query(None),
    include_stale: bool = Query(False),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Insight).order_by(Insight.created_at.desc())

    if domain:
        query = query.where(Insight.domain == domain)
    if not include_stale:
        query = query.where(Insight.stale.is_(False))

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{insight_id}", response_model=InsightResponse)
async def get_insight(insight_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Insight).where(Insight.id == insight_id))
    insight = result.scalar_one_or_none()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    return insight


@router.post("/", response_model=InsightResponse)
async def create_insight(body: InsightCreate, db: AsyncSession = Depends(get_db)):
    # Mark previous insights for this domain as stale
    await db.execute(
        update(Insight)
        .where(Insight.domain == body.domain, Insight.stale.is_(False))
        .values(stale=True)
    )

    insight = Insight(
        domain=body.domain,
        title=body.title,
        ground_truth=body.ground_truth,
        trend_analysis=body.trend_analysis,
        prediction=body.prediction,
        action_items=body.action_items,
        confidence=body.confidence,
        sources=body.sources,
    )
    db.add(insight)
    await db.commit()
    await db.refresh(insight)
    return insight
