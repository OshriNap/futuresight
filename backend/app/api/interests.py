import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user_interest import UserInterest

router = APIRouter()


class InterestCreate(BaseModel):
    name: str
    description: str | None = None
    keywords: list[str]
    category: str | None = None
    priority: str = "medium"
    notification_enabled: bool = True


class InterestResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    keywords: list[str]
    category: str | None
    priority: str
    notification_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[InterestResponse])
async def list_interests(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserInterest).order_by(UserInterest.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=InterestResponse, status_code=201)
async def create_interest(data: InterestCreate, db: AsyncSession = Depends(get_db)):
    interest = UserInterest(**data.model_dump())
    db.add(interest)
    await db.commit()
    await db.refresh(interest)
    return interest


@router.put("/{interest_id}", response_model=InterestResponse)
async def update_interest(interest_id: uuid.UUID, data: InterestCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserInterest).where(UserInterest.id == interest_id))
    interest = result.scalar_one_or_none()
    if not interest:
        raise HTTPException(status_code=404, detail="Interest not found")
    for key, value in data.model_dump().items():
        setattr(interest, key, value)
    await db.commit()
    await db.refresh(interest)
    return interest


@router.delete("/{interest_id}", status_code=204)
async def delete_interest(interest_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserInterest).where(UserInterest.id == interest_id))
    interest = result.scalar_one_or_none()
    if not interest:
        raise HTTPException(status_code=404, detail="Interest not found")
    await db.delete(interest)
    await db.commit()
