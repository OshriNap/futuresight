"""API endpoints for meta-agent data: scratchpads, source reliability, methods."""

import uuid
import uuid as uuid_mod
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
    PredictionPattern,
    Scratchpad,
    SourceReliability,
)
from app.models.indicator import Indicator
from app.models.insight import Insight
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


@router.post("/scratchpad/digest")
async def digest_scratchpad(
    max_age_days: int = Query(default=7, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Archive old scratchpad entries into a rolling digest.

    Compresses entries older than max_age_days into a summary entry per agent_type,
    then archives the originals. Inspired by openevolve's meta-analysis digest.
    """
    from datetime import timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    result = await db.execute(
        select(Scratchpad)
        .where(Scratchpad.status == "active")
        .where(Scratchpad.created_at < cutoff)
        .order_by(Scratchpad.agent_type, Scratchpad.created_at.asc())
    )
    old_entries = result.scalars().all()

    if not old_entries:
        return {"status": "no_entries_to_digest", "archived": 0, "digests_created": 0}

    # Group by agent_type
    by_agent: dict[str, list] = {}
    for entry in old_entries:
        by_agent.setdefault(entry.agent_type, []).append(entry)

    digests_created = 0
    archived = 0

    for agent_type, entries in by_agent.items():
        # Build digest content
        lines = []
        categories = set()
        all_tags = set()
        for e in entries:
            lines.append(f"- [{e.category}/{e.priority}] {e.title}: {e.content[:200]}")
            categories.add(e.category)
            if e.tags:
                all_tags.update(e.tags)

        digest = Scratchpad(
            agent_type=agent_type,
            title=f"Digest: {len(entries)} entries from {agent_type} (before {cutoff.strftime('%Y-%m-%d')})",
            content="\n".join(lines),
            category="digest",
            priority="low",
            tags=sorted(all_tags)[:20],
            extra_data={
                "original_count": len(entries),
                "categories": sorted(categories),
                "date_range": {
                    "from": entries[0].created_at.isoformat() if entries[0].created_at else None,
                    "to": entries[-1].created_at.isoformat() if entries[-1].created_at else None,
                },
            },
        )
        db.add(digest)
        digests_created += 1

        # Archive originals
        for e in entries:
            e.status = "archived"
            archived += 1

    await db.commit()
    return {"status": "completed", "archived": archived, "digests_created": digests_created}


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


# --- Pattern Library ---

@router.get("/patterns")
async def list_patterns(
    status: str | None = None,
    pattern_type: str | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List prediction patterns from the pattern library."""
    query = select(PredictionPattern).order_by(PredictionPattern.updated_at.desc())
    if status:
        query = query.where(PredictionPattern.status == status)
    if pattern_type:
        query = query.where(PredictionPattern.pattern_type == pattern_type)
    if category:
        query = query.where(PredictionPattern.category == category)
    result = await db.execute(query)
    patterns = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "pattern_type": p.pattern_type,
            "description": p.description,
            "condition": p.condition,
            "times_seen": p.times_seen,
            "times_correct": p.times_correct,
            "accuracy": round(p.accuracy, 3) if p.accuracy else None,
            "avg_impact": round(p.avg_impact, 4) if p.avg_impact else None,
            "status": p.status,
            "category": p.category,
            "version": p.version,
            "discovered_by": p.discovered_by,
            "validated_at": p.validated_at.isoformat() if p.validated_at else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in patterns
    ]


@router.get("/patterns/summary")
async def patterns_summary(db: AsyncSession = Depends(get_db)):
    """Summary stats for the pattern library."""
    total = (await db.execute(select(func.count(PredictionPattern.id)))).scalar() or 0
    validated = (await db.execute(
        select(func.count(PredictionPattern.id)).where(PredictionPattern.status == "validated")
    )).scalar() or 0
    candidate = (await db.execute(
        select(func.count(PredictionPattern.id)).where(PredictionPattern.status == "candidate")
    )).scalar() or 0
    rejected = (await db.execute(
        select(func.count(PredictionPattern.id)).where(PredictionPattern.status == "rejected")
    )).scalar() or 0

    by_type = await db.execute(
        select(PredictionPattern.pattern_type, func.count(PredictionPattern.id))
        .group_by(PredictionPattern.pattern_type)
    )

    return {
        "total": total,
        "validated": validated,
        "candidate": candidate,
        "rejected": rejected,
        "by_type": {t: c for t, c in by_type.all()},
    }


# --- Trigger Meta Agents ---

@router.post("/trigger/{agent_type}")
async def trigger_meta_agent(agent_type: str):
    """Manually trigger a meta-agent run (simplified DB-only version)."""
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


@router.post("/categorize")
async def trigger_categorization(limit: int = 0):
    """Categorize uncategorized market sources using Ollama LLM."""
    from app.tasks.categorization_tasks import categorize_sources
    result = await categorize_sources(limit=limit)
    return {"status": "completed", "result": result}


@router.post("/score-predictions")
async def trigger_scoring():
    """Resolve markets and score predictions against actual outcomes."""
    from app.tasks.scoring_tasks import resolve_and_score
    result = await resolve_and_score()
    return {"status": "completed", "result": result}


@router.post("/backtest")
async def trigger_backtest(
    min_bettors: int = 10,
    max_markets: int = 200,
):
    """Run backtesting against resolved Manifold markets."""
    from app.tasks.backtest import run_backtest
    result = await run_backtest(min_bettors=min_bettors, max_markets=max_markets)
    return {"status": "completed", "result": result}


@router.post("/run-pipeline")
async def run_full_pipeline():
    """Run the full pipeline: collect -> sentiment -> match -> graph -> predict -> score."""
    results = {}

    from app.tasks.collection_tasks import collect_all
    results["collection"] = await collect_all()

    # Collect indicators
    try:
        from app.tasks.indicator_tasks import collect_indicators
        indicator_result = await collect_indicators()
        results["indicators"] = indicator_result
    except Exception as e:
        results["indicators"] = {"error": str(e)}

    from app.tasks.categorization_tasks import categorize_sources
    results["categorization"] = await categorize_sources()

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


@router.get("/insight-context/{interest_id}")
async def get_insight_context(interest_id: str, db: AsyncSession = Depends(get_db)):
    """Gather all data for an interest domain — used by Claude Code to generate insights."""
    from app.models.user_interest import UserInterest
    from app.models.source import Source

    interest = await db.get(UserInterest, uuid_mod.UUID(interest_id))
    if not interest:
        raise HTTPException(status_code=404, detail="Interest not found")

    # Recent indicators for this interest's series
    indicator_ids = []
    for spec in interest.indicators or []:
        if ":" in spec:
            _, series_id = spec.split(":", 1)
            indicator_ids.append(series_id)

    indicators_q = await db.execute(
        select(Indicator)
        .where(Indicator.series_id.in_(indicator_ids) if indicator_ids else Indicator.id.is_(None))
        .order_by(Indicator.release_date.desc())
        .limit(50)
    )
    indicators = indicators_q.scalars().all()

    # Recent market sources matching this interest
    keywords = interest.keywords or []
    market_filters = interest.market_filters or []
    search_terms = keywords + market_filters

    market_sources = []
    if search_terms:
        all_sources_q = await db.execute(
            select(Source)
            .where(Source.signal_type == "market_probability")
            .order_by(Source.updated_at.desc())
            .limit(500)
        )
        all_sources = all_sources_q.scalars().all()
        for s in all_sources:
            title_lower = (s.title or "").lower()
            if any(term.lower() in title_lower for term in search_terms):
                market_sources.append(s)
                if len(market_sources) >= 20:
                    break

    # Recent news sources
    news_sources = []
    if search_terms:
        news_q = await db.execute(
            select(Source)
            .where(Source.signal_type.in_(["news", "engagement"]))
            .order_by(Source.updated_at.desc())
            .limit(500)
        )
        all_news = news_q.scalars().all()
        for s in all_news:
            title_lower = (s.title or "").lower()
            if any(term.lower() in title_lower for term in search_terms):
                news_sources.append(s)
                if len(news_sources) >= 20:
                    break

    # Previous insights for context
    prev_insights_q = await db.execute(
        select(Insight)
        .where(Insight.domain == (interest.category or interest.name))
        .order_by(Insight.created_at.desc())
        .limit(3)
    )
    prev_insights = prev_insights_q.scalars().all()

    return {
        "interest": {
            "id": str(interest.id),
            "name": interest.name,
            "category": interest.category,
            "region": interest.region,
            "keywords": interest.keywords,
        },
        "indicators": [
            {"series_id": i.series_id, "name": i.name, "value": i.value, "unit": i.unit, "period": i.period, "agency": i.source_agency}
            for i in indicators
        ],
        "market_sources": [
            {"id": str(s.id), "title": s.title, "platform": s.platform, "probability": s.current_market_probability, "category": s.category}
            for s in market_sources
        ],
        "news_sources": [
            {"id": str(s.id), "title": s.title, "platform": s.platform, "sentiment": (s.raw_data or {}).get("sentiment")}
            for s in news_sources
        ],
        "previous_insights": [
            {"title": i.title, "created_at": str(i.created_at), "stale": i.stale, "ground_truth": i.ground_truth[:200]}
            for i in prev_insights
        ],
    }


@router.post("/collect-indicators")
async def trigger_collect_indicators():
    """Trigger indicator collection from government sources."""
    from app.tasks.indicator_tasks import collect_indicators
    result = await collect_indicators()
    return {"status": "ok", "results": result}


@router.post("/generate-insights")
async def trigger_generate_insights():
    """Generate draft insights for all enabled interests using local Ollama."""
    from app.tasks.insight_tasks import generate_insights
    result = await generate_insights()
    return {"status": "completed", "result": result}


@router.post("/generate-insight/{interest_id}")
async def trigger_single_insight(interest_id: str):
    """Generate a draft insight for a single interest using local Ollama."""
    from app.tasks.insight_tasks import generate_single_insight
    result = await generate_single_insight(interest_id)
    return {"status": "completed", "result": result}
