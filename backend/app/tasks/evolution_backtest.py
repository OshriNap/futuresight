"""Evolution backtest — fast-track evolution using already-resolved markets.

Instead of waiting weeks for markets to resolve, re-runs the prediction pipeline
with different genome params on historical resolved sources and scores immediately.
Runs multiple generations in minutes instead of weeks.
"""

import json
import logging
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.evolution.defaults import DEFAULT_GENOME
from app.evolution.engine import EvolutionEngine
from app.models.evolution import EvolutionRun, StrategyGenome
from app.models.price_history import PriceSnapshot
from app.models.source import Source
from app.tasks.prediction_tasks import (
    SPORTS_KEYWORDS,
    _find_cross_market,
    _get_news_sentiment,
    _guess_category,
    _is_sports_or_entertainment,
)
from app.tasks.scoring_tasks import outcomes_first
from app.tools.base_tool import ToolInput
from app.tools.tool_registry import registry

logger = logging.getLogger(__name__)


async def _build_resolved_dataset(db: AsyncSession) -> list[dict]:
    """Build dataset of resolved sources with their signals and actual outcomes."""
    result = await db.execute(
        select(Source)
        .where(Source.resolved_at.isnot(None))
        .where(Source.actual_outcome.isnot(None))
        .where(Source.signal_type == "market_probability")
        .where(Source.current_market_probability.isnot(None))
    )
    sources = result.scalars().all()

    dataset = []
    for source in sources:
        raw = source.raw_data or {}
        slug = raw.get("slug", "")

        if _is_sports_or_entertainment(source.title, slug):
            continue

        liquidity = raw.get("liquidityNum", 0) or raw.get("totalLiquidity", 0)
        if liquidity < 500:
            continue

        # Build signals (same logic as generate_predictions)
        signals = {
            "market_probability": source.current_market_probability,
            "market_volume": raw.get("volumeNum", 0) or raw.get("volume", 0),
            "bettor_count": raw.get("uniqueBettorCount", 0),
        }

        outcomes = raw.get("outcomes", [])
        prices = raw.get("outcomePrices", [])
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except (json.JSONDecodeError, TypeError):
                outcomes = []
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except (json.JSONDecodeError, TypeError):
                prices = []
        if len(prices) >= 2:
            signals["outcome_prices"] = {
                outcomes[i]: float(prices[i])
                for i in range(min(len(outcomes), len(prices)))
            }

        # Price history
        history_result = await db.execute(
            select(PriceSnapshot)
            .where(PriceSnapshot.source_id == source.id)
            .order_by(PriceSnapshot.recorded_at.asc())
            .limit(50)
        )
        snapshots = history_result.scalars().all()
        if len(snapshots) >= 3:
            signals["probability_history"] = [
                {"timestamp": s.recorded_at.isoformat(), "probability": s.probability}
                for s in snapshots
            ]

        # News sentiment
        news_sentiment = await _get_news_sentiment(db, source)
        if news_sentiment is not None:
            signals["news_sentiment"] = news_sentiment

        # Matched sources for NLI
        matched_sources = raw.get("matched_sources", [])
        if matched_sources:
            signals["matched_sources"] = matched_sources

        # Cross-market
        cross_market = await _find_cross_market(db, source)
        if cross_market:
            signals["market_probabilities"] = cross_market

        category = source.category or _guess_category(source.title)

        time_horizon = "medium"
        if source.resolution_date:
            res_date = source.resolution_date
            if res_date.tzinfo is None:
                res_date = res_date.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days = (res_date - now).days
            if days <= 7:
                time_horizon = "short"
            elif days > 90:
                time_horizon = "long"
            signals["time_decay"] = max(0.0, min(1.0, 1.0 - days / 365))

        # Actual outcome for scoring
        actual = 1.0 if source.actual_outcome in ("yes", outcomes_first(source)) else 0.0

        dataset.append({
            "source_id": source.id,
            "title": source.title,
            "signals": signals,
            "category": category,
            "time_horizon": time_horizon,
            "actual": actual,
            "metadata": {"source_id": source.id},
        })

    return dataset


async def _evaluate_genome_on_dataset(
    genome_data: dict,
    dataset: list[dict],
    performance_data: dict | None = None,
) -> tuple[float, int]:
    """Run prediction tools with genome params on dataset, return avg Brier and count."""
    brier_scores = []

    for item in dataset:
        tool_input = ToolInput(
            question=item["title"],
            category=item["category"],
            current_signals=item["signals"],
            time_horizon=item["time_horizon"],
            metadata=item["metadata"],
            genome_params=genome_data,
        )

        try:
            tool_names = registry.select_tools(tool_input, performance_data)
            results = await registry.run_tools(tool_input, tool_names, performance_data)
            if not results:
                continue
            output = registry.ensemble_prediction(results, genome_params=genome_data)
            brier = (output.probability - item["actual"]) ** 2
            brier_scores.append(brier)
        except Exception as e:
            logger.debug(f"Backtest tool error on '{item['title'][:50]}': {e}")
            continue

    if not brier_scores:
        return 1.0, 0

    avg_brier = sum(brier_scores) / len(brier_scores)
    return round(avg_brier, 6), len(brier_scores)


async def run_evolution_backtest(generations: int = 10, candidates_per_gen: int = 5) -> dict:
    """Run multiple evolution generations against resolved historical data.

    Args:
        generations: Number of evolution generations to run
        candidates_per_gen: Candidates to create per generation

    Returns:
        Summary with generation-by-generation results
    """
    engine = EvolutionEngine()

    # Build dataset once
    async with async_session() as db:
        dataset = await _build_resolved_dataset(db)

    if not dataset:
        return {"error": "No resolved sources available for backtesting"}

    logger.info(f"Evolution backtest: {len(dataset)} resolved sources, {generations} generations")

    # Load performance data
    from app.tasks.scoring_tasks import build_performance_data
    try:
        performance_data = await build_performance_data()
    except Exception:
        performance_data = None

    # Ensure champion exists
    async with async_session() as db:
        champion = await engine.ensure_champion(db)
        await db.commit()

    results_log = []

    for gen in range(generations):
        async with async_session() as db:
            # Get current champion
            champ_result = await db.execute(
                select(StrategyGenome).where(StrategyGenome.status == "champion")
            )
            champion = champ_result.scalar_one_or_none()
            if not champion:
                break

            # Evaluate champion
            champ_brier, champ_n = await _evaluate_genome_on_dataset(
                champion.genome_data, dataset, performance_data,
            )
            champion.fitness = champ_brier
            champion.scored_predictions = champ_n

            # Try LLM-guided mutation for first candidate
            llm_mutations = await engine._get_llm_guided_mutations(db, champion)

            # Create and evaluate candidates
            best_candidate = None
            best_brier = champ_brier
            candidates_info = []

            for i in range(candidates_per_gen):
                if i == 0 and llm_mutations:
                    from app.evolution.llm_advisor import apply_guided_mutations
                    mutated_data = apply_guided_mutations(champion.genome_data, llm_mutations)
                    source_type = "llm_guided"
                else:
                    # Backtest uses wider mutations (5-10 params) to explore more aggressively
                    import random
                    mutated_data = engine.mutate(champion, n_params=random.randint(5, 10))
                    source_type = "random"

                # Evaluate immediately on the dataset
                cand_brier, cand_n = await _evaluate_genome_on_dataset(
                    mutated_data, dataset, performance_data,
                )

                candidates_info.append({
                    "source": source_type,
                    "brier": cand_brier,
                    "scored": cand_n,
                })

                if cand_brier < best_brier - 0.0001:  # Must beat by 0.0001 in backtest
                    best_brier = cand_brier
                    best_candidate = mutated_data

            # Promote best candidate if it beats champion
            promoted = False
            improvement = 0.0
            if best_candidate and best_brier < champ_brier - 0.0001:
                champion.status = "retired"
                champion.notes = (
                    f"Backtest retired: Brier {champ_brier:.4f} → {best_brier:.4f} "
                    f"(gen {champion.generation})"
                )

                new_champ = StrategyGenome(
                    genome_data=best_candidate,
                    reframe_strategies=engine.mutate_reframes(champion.reframe_strategies),
                    fitness=best_brier,
                    status="champion",
                    generation=champion.generation + 1,
                    parent_id=champion.id,
                    scored_predictions=len(dataset),
                    notes=f"Backtest promoted: Brier {best_brier:.4f} (from {champ_brier:.4f})",
                )
                db.add(new_champ)
                promoted = True
                improvement = champ_brier - best_brier

            # Log evolution run
            run = EvolutionRun(
                generation=champion.generation + (1 if promoted else 0),
                candidates_created=candidates_per_gen,
                candidates_retired=0,
                candidates_promoted=1 if promoted else 0,
                champion_fitness=best_brier if promoted else champ_brier,
                improvement=round(improvement, 6) if promoted else None,
                details={
                    "mode": "backtest",
                    "dataset_size": len(dataset),
                    "candidates": candidates_info,
                },
            )
            db.add(run)
            await db.commit()

            gen_result = {
                "generation": champion.generation + (1 if promoted else 0),
                "champion_brier": round(champ_brier, 6),
                "best_candidate_brier": round(best_brier, 6),
                "promoted": promoted,
                "improvement": round(improvement, 6),
                "candidates": candidates_info,
            }
            results_log.append(gen_result)

            status = "PROMOTED" if promoted else "no improvement"
            logger.info(
                f"Backtest gen {gen}: champion={champ_brier:.4f}, "
                f"best={best_brier:.4f} [{status}]"
            )

            if not promoted:
                # Still create candidates even if no promotion — try harder mutations
                pass

    # Final champion
    async with async_session() as db:
        final = await engine.get_champion(db)
        final_data = {
            "generation": final.generation if final else 0,
            "fitness": round(final.fitness, 6) if final and final.fitness else None,
        }

        # Compute diff from defaults
        diffs = {}
        if final and final.genome_data:
            for key, val in final.genome_data.items():
                default = DEFAULT_GENOME.get(key)
                if default is not None and val != default:
                    diffs[key] = {
                        "value": round(val, 6) if isinstance(val, float) else val,
                        "default": default,
                        "delta": round(val - default, 6),
                    }

    return {
        "dataset_size": len(dataset),
        "generations_run": len(results_log),
        "results": results_log,
        "final_champion": final_data,
        "evolved_params": diffs,
        "total_improvement": round(
            results_log[0]["champion_brier"] - results_log[-1]["best_candidate_brier"], 6
        ) if results_log else 0,
    }
