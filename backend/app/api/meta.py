"""API endpoints for meta-agent data: scratchpads, source reliability, methods."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.meta import (
    FeatureImportance,
    MetaAgentRun,
    PredictionMethod,
    Scratchpad,
    SourceReliability,
)

router = APIRouter()


# --- Scratchpad ---

class ScratchpadResponse(BaseModel):
    id: uuid.UUID
    agent_type: str
    title: str
    content: str
    category: str
    priority: str
    status: str
    tags: list[str] | None
    metadata: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.get("/scratchpad", response_model=list[ScratchpadResponse])
async def list_scratchpad(
    agent_type: str | None = None,
    category: str | None = None,
    status: str = "active",
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Scratchpad)
        .where(Scratchpad.status == status)
        .order_by(Scratchpad.created_at.desc())
        .limit(limit)
    )
    if agent_type:
        query = query.where(Scratchpad.agent_type == agent_type)
    if category:
        query = query.where(Scratchpad.category == category)
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/scratchpad/{entry_id}/status")
async def update_scratchpad_status(
    entry_id: uuid.UUID, status: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Scratchpad).where(Scratchpad.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    entry.status = status
    await db.commit()
    return {"status": "updated"}


# --- Source Reliability ---

class SourceReliabilityResponse(BaseModel):
    id: uuid.UUID
    platform: str
    reliability_score: float
    accuracy_rate: float | None
    timeliness_score: float | None
    coverage_score: float | None
    sample_size: int
    notes: str | None
    evaluated_at: datetime

    model_config = {"from_attributes": True}


@router.get("/sources/reliability", response_model=list[SourceReliabilityResponse])
async def get_source_reliability(db: AsyncSession = Depends(get_db)):
    # Get latest reliability record per platform
    from sqlalchemy import func
    subq = (
        select(SourceReliability.platform, func.max(SourceReliability.evaluated_at).label("latest"))
        .group_by(SourceReliability.platform)
        .subquery()
    )
    query = (
        select(SourceReliability)
        .join(subq, (SourceReliability.platform == subq.c.platform) & (SourceReliability.evaluated_at == subq.c.latest))
    )
    result = await db.execute(query)
    return result.scalars().all()


# --- Prediction Methods ---

class PredictionMethodResponse(BaseModel):
    id: uuid.UUID
    name: str
    method_type: str
    description: str
    is_active: bool
    avg_accuracy: float | None
    best_categories: list[str] | None
    worst_categories: list[str] | None
    total_uses: int
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/methods", response_model=list[PredictionMethodResponse])
async def list_methods(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PredictionMethod).order_by(PredictionMethod.name))
    return result.scalars().all()


# --- Meta Agent Runs ---

class MetaAgentRunResponse(BaseModel):
    id: uuid.UUID
    agent_type: str
    trigger: str
    input_summary: str | None
    output_summary: str
    actions_taken: list[str] | None
    scratchpad_entries_created: int
    duration_seconds: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/runs", response_model=list[MetaAgentRunResponse])
async def list_meta_runs(
    agent_type: str | None = None,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(MetaAgentRun).order_by(MetaAgentRun.created_at.desc()).limit(limit)
    if agent_type:
        query = query.where(MetaAgentRun.agent_type == agent_type)
    result = await db.execute(query)
    return result.scalars().all()


# --- Trigger Meta Agents ---

@router.post("/trigger/{agent_type}")
async def trigger_meta_agent(agent_type: str):
    """Manually trigger a meta-agent run."""
    from app.tasks.meta_tasks import (
        run_feature_ideator,
        run_method_researcher,
        run_source_evaluator,
        run_strategy_optimizer,
    )

    task_map = {
        "source_evaluator": run_source_evaluator,
        "strategy_optimizer": run_strategy_optimizer,
        "method_researcher": run_method_researcher,
        "feature_ideator": run_feature_ideator,
    }
    task_fn = task_map.get(agent_type)
    if not task_fn:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {agent_type}")

    task_fn.delay()
    return {"status": "triggered", "agent_type": agent_type}
