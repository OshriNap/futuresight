"""Prediction scoring — resolves markets and computes accuracy metrics.

Checks Polymarket for resolved markets, updates Source outcomes,
scores linked Predictions using Brier score and calibration error,
and builds performance_data for the ToolRegistry feedback loop.
"""

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.prediction import Prediction, PredictionScore
from app.models.source import Source

logger = logging.getLogger(__name__)

GAMMA_API_URL = "https://gamma-api.polymarket.com"


async def resolve_markets() -> dict:
    """Check Polymarket for resolved markets and update Source outcomes.

    Returns dict with counts of newly resolved sources.
    """
    resolved_count = 0
    checked = 0

    async with async_session() as db:
        # Get market sources that haven't been resolved yet
        result = await db.execute(
            select(Source)
            .where(Source.signal_type == "market_probability")
            .where(Source.resolved_at.is_(None))
        )
        unresolved = result.scalars().all()

        if not unresolved:
            return {"checked": 0, "resolved": 0, "message": "No unresolved markets"}

        # Batch check resolved markets from both platforms
        closed_by_id: dict[str, dict] = {}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Polymarket
                try:
                    response = await client.get(
                        f"{GAMMA_API_URL}/markets",
                        params={"closed": "true", "limit": 100, "order": "endDate", "ascending": "false"},
                    )
                    response.raise_for_status()
                    for m in response.json():
                        mid = str(m.get("id", ""))
                        if mid:
                            closed_by_id[mid] = {**m, "_platform": "polymarket"}
                except httpx.HTTPError as e:
                    logger.warning(f"Polymarket resolution check failed: {e}")

                # Manifold — check each unresolved source individually (batch not available)
                manifold_sources = [s for s in unresolved if s.platform == "manifold"]
                for source in manifold_sources[:50]:  # limit API calls
                    try:
                        r = await client.get(f"https://api.manifold.markets/v0/market/{source.external_id}")
                        if r.status_code == 200:
                            m = r.json()
                            if m.get("isResolved"):
                                closed_by_id[source.external_id] = {**m, "_platform": "manifold"}
                    except httpx.HTTPError:
                        pass
        except Exception as e:
            logger.error(f"Resolution check failed: {e}")
            return {"checked": 0, "resolved": 0, "error": str(e)}

        # Match against our unresolved sources
        for source in unresolved:
            checked += 1
            market = closed_by_id.get(source.external_id)
            if not market:
                continue

            platform = market.get("_platform", source.platform)
            actual_outcome = None

            if platform == "manifold":
                # Manifold: resolution is explicit
                resolution = market.get("resolution")
                if resolution == "YES":
                    actual_outcome = "yes"
                elif resolution == "NO":
                    actual_outcome = "no"
                else:
                    continue  # CANCEL, MKT, or other — skip

            else:
                # Polymarket: determine from resolved prices
                outcome_prices = market.get("outcomePrices", [])
                outcomes = market.get("outcomes", [])

                if isinstance(outcome_prices, str):
                    import json
                    try:
                        outcome_prices = json.loads(outcome_prices)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if isinstance(outcomes, str):
                    import json
                    try:
                        outcomes = json.loads(outcomes)
                    except (json.JSONDecodeError, TypeError):
                        continue

                if not outcome_prices or not outcomes:
                    continue

                try:
                    prices = [float(p) for p in outcome_prices]
                except (ValueError, TypeError):
                    continue

                if not any(p > 0.95 or p < 0.05 for p in prices):
                    continue

                winning_idx = max(range(len(prices)), key=lambda i: prices[i])
                actual_outcome = (outcomes[winning_idx] if winning_idx < len(outcomes) else "yes").lower()

            if actual_outcome:
                source.resolved_at = datetime.now(timezone.utc)
                source.actual_outcome = actual_outcome
                resolved_count += 1

        await db.commit()

    logger.info(f"Resolution check: checked={checked}, resolved={resolved_count}")
    return {"checked": checked, "resolved": resolved_count}


async def score_predictions() -> dict:
    """Score predictions against resolved markets.

    Computes Brier score and absolute error for predictions
    whose sources have been resolved. Returns scoring summary.
    """
    scored = 0
    skipped = 0

    async with async_session() as db:
        # Get predictions with resolved sources that haven't been scored yet
        result = await db.execute(
            select(Prediction)
            .join(Source, Prediction.source_id == Source.id)
            .where(Source.resolved_at.isnot(None))
            .where(Source.actual_outcome.isnot(None))
            .options(selectinload(Prediction.source), selectinload(Prediction.scores))
        )
        predictions = result.scalars().all()

        for pred in predictions:
            # Skip if already scored
            if pred.scores:
                skipped += 1
                continue

            source = pred.source
            if not source or not source.actual_outcome:
                continue

            # Convert actual outcome to binary (1.0 = yes/first outcome won)
            actual = 1.0 if source.actual_outcome in ("yes", outcomes_first(source)) else 0.0

            # Brier score: (forecast - actual)^2
            brier = (pred.confidence - actual) ** 2

            # Absolute error
            abs_error = abs(pred.confidence - actual)

            score = PredictionScore(
                prediction_id=pred.id,
                brier_score=round(brier, 6),
                absolute_error=round(abs_error, 6),
            )
            db.add(score)

            # Mark prediction as resolved
            pred.resolved_at = source.resolved_at

            scored += 1

        await db.commit()

    logger.info(f"Scoring: scored={scored}, already_scored={skipped}")
    return {"scored": scored, "skipped": skipped, "total": scored + skipped}


def outcomes_first(source: Source) -> str:
    """Get the first outcome label from source raw_data (lowercased)."""
    raw = source.raw_data or {}
    outcomes = raw.get("outcomes", [])
    if isinstance(outcomes, str):
        import json
        try:
            outcomes = json.loads(outcomes)
        except (json.JSONDecodeError, TypeError):
            return ""
    return outcomes[0].lower() if outcomes else ""


async def build_performance_data() -> dict:
    """Build per-tool performance data from scored predictions.

    Queries PredictionScore + Prediction.data_signals to compute
    average Brier score per tool. Returns format expected by
    ToolRegistry.select_tools():
        {tool_name: {"brier_score": float, "count": int}}
    """
    from collections import defaultdict

    tool_scores: dict[str, list[float]] = defaultdict(list)

    async with async_session() as db:
        result = await db.execute(
            select(Prediction, PredictionScore)
            .join(PredictionScore, PredictionScore.prediction_id == Prediction.id)
        )
        rows = result.all()

        for pred, score in rows:
            ds = pred.data_signals or {}
            tools_used = ds.get("tools_used", [])
            for tool_name in tools_used:
                tool_scores[tool_name].append(score.brier_score)

    performance_data = {}
    for tool_name, scores in tool_scores.items():
        performance_data[tool_name] = {
            "brier_score": sum(scores) / len(scores),
            "count": len(scores),
        }

    return performance_data


async def resolve_and_score() -> dict:
    """Full pipeline: resolve markets, then score predictions, then build perf data, then evolve."""
    resolution = await resolve_markets()
    scoring = await score_predictions()
    performance = await build_performance_data()

    # Post-scoring: run evolution cycle to evaluate genomes
    evolution_result = None
    if scoring.get("scored", 0) > 0:
        try:
            from app.tasks.evolution_tasks import run_evolution_cycle
            evolution_result = await run_evolution_cycle()
        except Exception as e:
            logger.warning(f"Evolution cycle failed: {e}")
            evolution_result = {"error": str(e)}

    return {
        "resolution": resolution,
        "scoring": scoring,
        "performance_data": performance,
        "tools_with_data": list(performance.keys()),
        "evolution": evolution_result,
    }
