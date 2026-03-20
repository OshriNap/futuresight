import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.indicator import Indicator

router = APIRouter()


class IndicatorResponse(BaseModel):
    id: uuid.UUID
    source_agency: str
    series_id: str
    name: str
    category: str | None
    region: str | None
    value: float
    unit: str | None
    period: str
    release_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[IndicatorResponse])
async def list_indicators(
    agency: str | None = Query(None),
    category: str | None = Query(None),
    region: str | None = Query(None),
    series_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(Indicator).order_by(Indicator.release_date.desc())

    if agency:
        query = query.where(Indicator.source_agency == agency)
    if category:
        query = query.where(Indicator.category == category)
    if region:
        query = query.where(Indicator.region == region)
    if series_id:
        query = query.where(Indicator.series_id == series_id)

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/history/{series_id}")
async def indicator_history(
    series_id: str,
    agency: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Indicator)
        .where(Indicator.series_id == series_id)
        .order_by(Indicator.period.asc())
    )
    if agency:
        query = query.where(Indicator.source_agency == agency)

    result = await db.execute(query)
    rows = result.scalars().all()

    return {
        "series_id": series_id,
        "agency": rows[0].source_agency if rows else agency,
        "name": rows[0].name if rows else series_id,
        "unit": rows[0].unit if rows else None,
        "data": [
            {"period": r.period, "value": r.value, "release_date": str(r.release_date) if r.release_date else None}
            for r in rows
        ],
    }
