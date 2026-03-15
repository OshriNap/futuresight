"""API endpoints for meta-agent data: scratchpads, source reliability, methods."""

import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.meta import (
    FeatureImportance,
    MetaAgentRun,
    PredictionMethod,
    Scratchpad,
    SourceReliability,
)
from app.models.prediction import Prediction, PredictionScore
from app.models.source import Source

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
    extra_data: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScratchpadCreate(BaseModel):
    agent_type: str
    title: str
    content: str
    category: str = "insight"
    priority: str = "medium"
    tags: list[str] | None = None
    extra_data: dict | None = None


@router.post("/scratchpad", response_model=ScratchpadResponse, status_code=201)
async def create_scratchpad(
    data: ScratchpadCreate, db: AsyncSession = Depends(get_db)
):
    """Create a new scratchpad entry. Used by Claude Code scheduled tasks."""
    entry = Scratchpad(
        agent_type=data.agent_type,
        title=data.title,
        content=data.content,
        category=data.category,
        priority=data.priority,
        tags=data.tags,
        extra_data=data.extra_data,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


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


class MetaRunCreate(BaseModel):
    agent_type: str
    trigger: str = "claude_code_scheduled_task"
    input_summary: str | None = None
    output_summary: str
    actions_taken: list[str] | None = None
    scratchpad_entries_created: int = 0
    duration_seconds: float | None = None


@router.post("/runs", response_model=MetaAgentRunResponse, status_code=201)
async def create_meta_run(
    data: MetaRunCreate, db: AsyncSession = Depends(get_db)
):
    """Log a meta-agent run. Used by Claude Code scheduled tasks."""
    run = MetaAgentRun(
        agent_type=data.agent_type,
        trigger=data.trigger,
        input_summary=data.input_summary,
        output_summary=data.output_summary,
        actions_taken=data.actions_taken,
        scratchpad_entries_created=data.scratchpad_entries_created,
        duration_seconds=data.duration_seconds,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


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


# --- System Stats ---

@router.get("/stats")
async def get_system_stats(db: AsyncSession = Depends(get_db)):
    """System-wide stats for Claude Code scheduled tasks to get context."""
    source_count = (await db.execute(select(func.count(Source.id)))).scalar() or 0
    pred_count = (await db.execute(select(func.count(Prediction.id)))).scalar() or 0
    avg_brier = (await db.execute(select(func.avg(PredictionScore.brier_score)))).scalar()
    scored_count = (await db.execute(select(func.count(PredictionScore.id)))).scalar() or 0

    platforms = await db.execute(select(Source.platform, func.count(Source.id)).group_by(Source.platform))
    platform_counts = {row[0]: row[1] for row in platforms.all()}

    return {
        "total_sources": source_count,
        "total_predictions": pred_count,
        "scored_predictions": scored_count,
        "avg_brier_score": round(avg_brier, 4) if avg_brier else None,
        "platforms": platform_counts,
    }


# --- Trigger Meta Agents ---

@router.post("/trigger/{agent_type}")
async def trigger_meta_agent(agent_type: str):
    """Manually trigger a meta-agent run (simplified DB-only version)."""
    from app.tasks.meta_tasks import (
        run_method_researcher,
        run_source_evaluator,
        run_strategy_optimizer,
    )

    task_map = {
        "source_evaluator": run_source_evaluator,
        "strategy_optimizer": run_strategy_optimizer,
        "method_researcher": run_method_researcher,
    }
    task_fn = task_map.get(agent_type)
    if not task_fn:
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {agent_type}. Thinking is handled by Claude Code scheduled tasks.")

    result = await task_fn()
    return {"status": "completed", "agent_type": agent_type, "result": result}


@router.post("/collect/{collector_name}")
async def trigger_collection(
    collector_name: str, background_tasks: BackgroundTasks = None,
):
    """Trigger a data collection run (runs in background)."""
    from app.tasks.collection_tasks import (
        collect_all,
        collect_gdelt,
        collect_manifold,
        collect_polymarket,
        collect_reddit,
    )

    collector_map = {
        "polymarket": collect_polymarket,
        "manifold": collect_manifold,
        "gdelt": collect_gdelt,
        "reddit": collect_reddit,
        "all": collect_all,
    }
    fn = collector_map.get(collector_name)
    if not fn:
        raise HTTPException(status_code=400, detail=f"Unknown collector: {collector_name}")

    result = await fn()
    return {"status": "completed", "collector": collector_name, "result": result}


@router.post("/generate-predictions")
async def trigger_predictions():
    """Generate predictions from collected sources using the tool registry."""
    from app.tasks.prediction_tasks import generate_predictions
    result = await generate_predictions()
    return {"status": "completed", "result": result}


@router.post("/build-graph")
async def trigger_graph_build():
    """Build event graph nodes and causal edges from collected sources."""
    from app.tasks.graph_tasks import build_event_graph
    result = await build_event_graph()
    return {"status": "completed", "result": result}


@router.post("/match-sources")
async def trigger_matching():
    """Match news/reddit sources to market questions via GPU sentence embeddings."""
    from app.tasks.embedding_tasks import match_sources
    result = await match_sources()
    return {"status": "completed", "result": result}


@router.post("/score-predictions")
async def trigger_scoring():
    """Resolve markets and score predictions against actual outcomes."""
    from app.tasks.scoring_tasks import resolve_and_score
    result = await resolve_and_score()
    return {"status": "completed", "result": result}


@router.post("/run-pipeline")
async def run_full_pipeline():
    """Run the full pipeline: collect -> sentiment -> match -> graph -> predict -> score."""
    results = {}

    from app.tasks.collection_tasks import collect_all
    results["collection"] = await collect_all()

    from app.tasks.embedding_tasks import match_sources
    results["matching"] = await match_sources()

    from app.tasks.graph_tasks import build_event_graph
    results["graph"] = await build_event_graph()

    from app.tasks.prediction_tasks import generate_predictions
    results["predictions"] = await generate_predictions()

    from app.tasks.scoring_tasks import resolve_and_score
    results["scoring"] = await resolve_and_score()

    return {"status": "completed", "result": results}


@router.post("/analyze-sentiment")
async def trigger_sentiment(
    platform: str | None = None,
    force: bool = False,
):
    """Run batch sentiment analysis on sources using local GPU."""
    from app.tasks.sentiment_tasks import analyze_sentiment
    result = await analyze_sentiment(platform=platform, force=force)
    return {"status": "completed", "result": result}
