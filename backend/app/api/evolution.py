"""API endpoints for the evolution system — genome monitoring and control.

Two LLM integration patterns:
- Guided mutation: local Ollama qwen2.5-coder (fast, inline during evolution)
- Meta-analysis: Claude Code scheduled task fetches context, reasons with cloud model,
  POSTs guidance back
"""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.evolution import EvolutionRun, StrategyGenome

router = APIRouter()


@router.get("/genomes")
async def list_genomes(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all genomes with fitness info."""
    query = select(StrategyGenome).order_by(StrategyGenome.created_at.desc())
    if status:
        query = query.where(StrategyGenome.status == status)
    result = await db.execute(query)
    genomes = result.scalars().all()
    return [
        {
            "id": str(g.id),
            "status": g.status,
            "generation": g.generation,
            "fitness": round(g.fitness, 6) if g.fitness is not None else None,
            "scored_predictions": g.scored_predictions,
            "parent_id": str(g.parent_id) if g.parent_id else None,
            "notes": g.notes,
            "created_at": g.created_at.isoformat() if g.created_at else None,
            "param_count": len(g.genome_data) if g.genome_data else 0,
        }
        for g in genomes
    ]


@router.get("/champion")
async def get_champion(db: AsyncSession = Depends(get_db)):
    """Get the current champion genome with full parameters."""
    result = await db.execute(
        select(StrategyGenome).where(StrategyGenome.status == "champion")
    )
    champion = result.scalar_one_or_none()
    if not champion:
        return {"status": "no_champion", "message": "Run /api/evolution/evolve to bootstrap"}

    return {
        "id": str(champion.id),
        "status": champion.status,
        "generation": champion.generation,
        "fitness": round(champion.fitness, 6) if champion.fitness is not None else None,
        "scored_predictions": champion.scored_predictions,
        "genome_data": champion.genome_data,
        "reframe_strategies": champion.reframe_strategies,
        "notes": champion.notes,
        "created_at": champion.created_at.isoformat() if champion.created_at else None,
    }


@router.post("/evolve")
async def trigger_evolution():
    """Trigger an evolution cycle: evaluate candidates, create new ones."""
    from app.tasks.evolution_tasks import run_evolution_cycle
    result = await run_evolution_cycle()
    return {"status": "completed", "result": result}


@router.get("/history")
async def evolution_history(
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get evolution run history."""
    result = await db.execute(
        select(EvolutionRun).order_by(EvolutionRun.created_at.desc()).limit(limit)
    )
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "generation": r.generation,
            "candidates_created": r.candidates_created,
            "candidates_retired": r.candidates_retired,
            "candidates_promoted": r.candidates_promoted,
            "champion_fitness": round(r.champion_fitness, 6) if r.champion_fitness is not None else None,
            "improvement": round(r.improvement, 6) if r.improvement is not None else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]


# ── Backtest evolution (fast-track using resolved markets) ──

@router.post("/backtest")
async def run_backtest_evolution(
    generations: int = Query(default=10, ge=1, le=50),
    candidates: int = Query(default=5, ge=2, le=20),
):
    """Run evolution against already-resolved markets for immediate parameter optimization.

    Instead of waiting weeks for markets to resolve, replays the prediction pipeline
    with different genome params on historical data. Runs N generations in minutes.
    """
    from app.tasks.evolution_backtest import run_evolution_backtest
    result = await run_evolution_backtest(generations=generations, candidates_per_gen=candidates)
    return {"status": "completed", "result": result}


# ── Ollama-powered guided mutation (local, fast) ──

@router.post("/propose-mutations")
async def propose_mutations(db: AsyncSession = Depends(get_db)):
    """Ask local Ollama qwen2.5-coder to propose mutations without creating candidates.

    Useful for previewing what the LLM would suggest before running a full cycle.
    """
    from app.evolution.llm_advisor import propose_guided_mutations

    result = await db.execute(
        select(StrategyGenome).where(StrategyGenome.status == "champion")
    )
    champion = result.scalar_one_or_none()
    if not champion:
        return {"status": "error", "message": "No champion genome exists"}

    hist_result = await db.execute(
        select(EvolutionRun).order_by(EvolutionRun.created_at.desc()).limit(10)
    )
    history = [
        {
            "generation": r.generation,
            "champion_fitness": r.champion_fitness,
            "candidates_created": r.candidates_created,
            "candidates_retired": r.candidates_retired,
            "candidates_promoted": r.candidates_promoted,
        }
        for r in hist_result.scalars().all()
    ]

    ret_result = await db.execute(
        select(StrategyGenome)
        .where(StrategyGenome.status == "retired")
        .order_by(StrategyGenome.created_at.desc())
        .limit(5)
    )
    retired = [
        {"generation": g.generation, "fitness": g.fitness, "genome_data": g.genome_data}
        for g in ret_result.scalars().all()
    ]

    mutations = await propose_guided_mutations(
        champion_data=champion.genome_data,
        champion_fitness=champion.fitness,
        history=history,
        retired_genomes=retired,
    )

    if mutations is None:
        return {"status": "error", "message": "Ollama unavailable or failed to parse response"}

    return {
        "status": "ok",
        "champion_fitness": round(champion.fitness, 6) if champion.fitness else None,
        "proposed_mutations": mutations,
    }


# ── Cloud LLM meta-analysis (via Claude Code scheduled task) ──

@router.get("/meta-analysis-context")
async def get_meta_analysis_context(db: AsyncSession = Depends(get_db)):
    """Provide full evolution context for a Claude Code scheduled task to analyze.

    The scheduled task fetches this, reasons about it with a strong cloud model,
    then POSTs guidance back to /api/evolution/meta-analysis-guidance.
    """
    from app.evolution.llm_advisor import build_meta_analysis_context

    result = await db.execute(
        select(StrategyGenome).where(StrategyGenome.status == "champion")
    )
    champion = result.scalar_one_or_none()
    if not champion:
        return {"status": "no_champion"}

    # All genomes
    genome_result = await db.execute(
        select(StrategyGenome).order_by(StrategyGenome.created_at.desc()).limit(20)
    )
    all_genomes = [
        {
            "generation": g.generation,
            "status": g.status,
            "fitness": g.fitness,
            "genome_data": g.genome_data,
        }
        for g in genome_result.scalars().all()
    ]

    # History
    hist_result = await db.execute(
        select(EvolutionRun).order_by(EvolutionRun.created_at.desc()).limit(20)
    )
    history = [
        {
            "generation": r.generation,
            "champion_fitness": r.champion_fitness,
            "candidates_created": r.candidates_created,
            "candidates_retired": r.candidates_retired,
            "candidates_promoted": r.candidates_promoted,
        }
        for r in hist_result.scalars().all()
    ]

    return build_meta_analysis_context(
        champion_data=champion.genome_data,
        champion_fitness=champion.fitness,
        all_genomes=all_genomes,
        history=history,
    )


class MetaAnalysisGuidance(BaseModel):
    """Guidance from Claude Code scheduled task after analyzing evolution context."""
    stuck_params: list[str] | None = None
    promising_directions: list[str] | None = None
    exploration_suggestions: list[str] | None = None
    risk_assessment: str | None = None
    recommended_sigma_changes: list[dict] | None = None
    recommended_mutations: list[dict] | None = None  # [{param, value, reason}]


@router.post("/meta-analysis-guidance")
async def receive_meta_analysis_guidance(
    guidance: MetaAnalysisGuidance,
    db: AsyncSession = Depends(get_db),
):
    """Receive meta-analysis guidance from a Claude Code scheduled task.

    Saves to scratchpad for visibility and optionally creates a guided candidate.
    """
    from app.models.meta import Scratchpad

    # Save analysis to scratchpad
    entry = Scratchpad(
        agent_type="evolution_meta",
        title="Meta-analysis guidance from cloud LLM",
        content=json.dumps(guidance.model_dump(exclude_none=True), indent=2),
        category="insight",
        priority="medium",
        tags=["evolution", "meta-analysis", "cloud-llm"],
        extra_data=guidance.model_dump(exclude_none=True),
    )
    db.add(entry)

    # If the guidance includes recommended mutations, create a candidate
    candidates_created = 0
    if guidance.recommended_mutations:
        from app.evolution.llm_advisor import apply_guided_mutations
        from app.evolution.defaults import DEFAULT_GENOME, MUTATION_RANGES

        champion_result = await db.execute(
            select(StrategyGenome).where(StrategyGenome.status == "champion")
        )
        champion = champion_result.scalar_one_or_none()

        if champion:
            # Validate and apply mutations
            valid_mutations = []
            for m in guidance.recommended_mutations:
                param = m.get("param", "")
                value = m.get("value")
                if param in MUTATION_RANGES and value is not None:
                    try:
                        value = float(value)
                        min_val, max_val, _ = MUTATION_RANGES[param]
                        value = max(min_val, min(max_val, value))
                        if isinstance(DEFAULT_GENOME.get(param), int):
                            value = int(round(value))
                        else:
                            value = round(value, 6)
                        valid_mutations.append({"param": param, "value": value, "reason": m.get("reason", "")})
                    except (ValueError, TypeError):
                        pass

            if valid_mutations:
                mutated_data = apply_guided_mutations(champion.genome_data, valid_mutations)
                reasons = "; ".join(m["reason"][:50] for m in valid_mutations[:3])

                candidate = StrategyGenome(
                    genome_data=mutated_data,
                    reframe_strategies=champion.reframe_strategies,
                    fitness=None,
                    status="candidate",
                    generation=champion.generation + 1,
                    parent_id=champion.id,
                    notes=f"Cloud LLM meta-analysis candidate: {reasons}",
                )
                db.add(candidate)
                candidates_created = 1

    await db.commit()

    return {
        "status": "ok",
        "scratchpad_saved": True,
        "candidates_created": candidates_created,
    }


# ── Genome detail ──

@router.get("/genome/{genome_id}")
async def get_genome_detail(genome_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get full details for a specific genome including all parameters."""
    result = await db.execute(
        select(StrategyGenome).where(StrategyGenome.id == genome_id)
    )
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Genome not found")

    from app.evolution.defaults import DEFAULT_GENOME
    diffs = {}
    if g.genome_data:
        for key, val in g.genome_data.items():
            default = DEFAULT_GENOME.get(key)
            if default is not None and val != default:
                diffs[key] = {"current": val, "default": default, "delta": round(val - default, 6)}

    return {
        "id": str(g.id),
        "status": g.status,
        "generation": g.generation,
        "fitness": round(g.fitness, 6) if g.fitness is not None else None,
        "scored_predictions": g.scored_predictions,
        "parent_id": str(g.parent_id) if g.parent_id else None,
        "genome_data": g.genome_data,
        "reframe_strategies": g.reframe_strategies,
        "mutations_from_default": diffs,
        "notes": g.notes,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }
