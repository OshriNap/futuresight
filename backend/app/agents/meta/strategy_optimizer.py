"""Strategy Optimizer Meta-Agent

Analyzes prediction performance patterns and optimizes the prediction strategy.

Responsibilities:
- Identify which prediction methods work best for which categories
- Optimize confidence calibration
- Detect systematic biases (overconfidence, underconfidence)
- Suggest ensemble strategy adjustments
- Track what works and what doesn't in the scratchpad
"""

import logging

from sqlalchemy import and_, func, select

from app.agents.meta.base_meta import BaseMetaAgent
from app.database import async_session
from app.models.prediction import Prediction, PredictionScore

logger = logging.getLogger(__name__)


class StrategyOptimizer(BaseMetaAgent):
    agent_type = "strategy_optimizer"

    async def think(self) -> dict:
        entries = []
        actions = []

        async with async_session() as db:
            # Analyze calibration by confidence bucket
            buckets = [(0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.0)]
            calibration_issues = []

            for low, high in buckets:
                result = await db.execute(
                    select(
                        func.avg(PredictionScore.brier_score),
                        func.count(PredictionScore.id),
                        func.avg(Prediction.confidence),
                    )
                    .join(Prediction, Prediction.id == PredictionScore.prediction_id)
                    .where(and_(Prediction.confidence >= low, Prediction.confidence < high))
                )
                row = result.one_or_none()
                if row and row[1] > 0:
                    avg_brier, count, avg_conf = row
                    if avg_brier is not None:
                        # Check calibration: high confidence should have low brier
                        expected_brier = (1 - avg_conf) * avg_conf  # theoretical minimum for calibrated predictions
                        ratio = avg_brier / expected_brier if expected_brier > 0 else 1
                        if ratio > 1.5 and count >= 5:
                            calibration_issues.append({
                                "bucket": f"{low:.0%}-{high:.0%}",
                                "avg_brier": avg_brier,
                                "count": count,
                                "ratio": ratio,
                            })

            if calibration_issues:
                worst = max(calibration_issues, key=lambda x: x["ratio"])
                entries.append({
                    "title": f"Calibration issue in {worst['bucket']} confidence bucket",
                    "content": f"Predictions in the {worst['bucket']} confidence range have "
                               f"Brier score {worst['avg_brier']:.3f} ({worst['count']} predictions), "
                               f"which is {worst['ratio']:.1f}x worse than expected. "
                               f"System may be {'overconfident' if float(worst['bucket'].split('-')[0].strip('%')) / 100 > 0.5 else 'underconfident'} "
                               f"in this range.",
                    "category": "insight",
                    "priority": "high",
                    "tags": ["calibration", "bias"],
                })
                actions.append(f"Detected calibration issues in {len(calibration_issues)} confidence buckets")

            # Analyze by time horizon
            horizon_result = await db.execute(
                select(
                    Prediction.time_horizon,
                    func.avg(PredictionScore.brier_score),
                    func.count(PredictionScore.id),
                )
                .join(PredictionScore, PredictionScore.prediction_id == Prediction.id)
                .group_by(Prediction.time_horizon)
            )
            horizons = horizon_result.all()
            if len(horizons) > 1:
                best = min(horizons, key=lambda x: x[1] or 999)
                worst = max(horizons, key=lambda x: x[1] or 0)
                if best[1] is not None and worst[1] is not None:
                    entries.append({
                        "title": f"Time horizon analysis: {best[0]} performs best",
                        "content": f"Best: {best[0]} (Brier: {best[1]:.3f}, n={best[2]}). "
                                   f"Worst: {worst[0]} (Brier: {worst[1]:.3f}, n={worst[2]}). "
                                   f"Consider allocating more resources to {worst[0]} predictions.",
                        "category": "insight",
                        "tags": ["time_horizon", "strategy"],
                    })

            # Read previous scratchpad for learning continuity
            prev_insights = await self.read_scratchpad(category="insight", limit=10)
            if prev_insights:
                entries.append({
                    "title": "Strategy evolution tracking",
                    "content": f"Reviewed {len(prev_insights)} previous insights. "
                               "Key themes: " + ", ".join(set(
                                   tag for p in prev_insights[:5] if p.tags for tag in p.tags
                               ))[:500],
                    "category": "todo",
                    "priority": "low",
                    "tags": ["meta_review"],
                })

        return {
            "summary": f"Analyzed calibration and strategy, found {len(entries)} insights",
            "actions": actions,
            "scratchpad_entries": entries,
        }
