"""Source Evaluator Meta-Agent

DB-only operations: computes reliability scores per platform.
All analytical thinking and insight generation is handled by Claude Code scheduled tasks.
"""

import logging

from sqlalchemy import func, select

from app.agents.meta.base_meta import BaseMetaAgent
from app.database import async_session
from app.models.meta import SourceReliability
from app.models.prediction import Prediction, PredictionScore
from app.models.source import Source

logger = logging.getLogger(__name__)


class SourceEvaluator(BaseMetaAgent):
    agent_type = "source_evaluator"

    async def think(self) -> dict:
        """Compute and save reliability scores. No insight generation - that's Claude Code's job."""
        actions = []

        async with async_session() as db:
            platform_stats = await db.execute(
                select(
                    Source.platform,
                    func.count(Source.id).label("total"),
                    func.count(Source.resolved_at).label("resolved"),
                )
                .group_by(Source.platform)
            )
            stats = platform_stats.all()

            accuracy_query = await db.execute(
                select(
                    Source.platform,
                    func.avg(PredictionScore.brier_score).label("avg_brier"),
                    func.count(PredictionScore.id).label("scored_count"),
                )
                .join(Prediction, Prediction.source_id == Source.id)
                .join(PredictionScore, PredictionScore.prediction_id == Prediction.id)
                .group_by(Source.platform)
            )
            accuracy_data = {row[0]: {"avg_brier": row[1], "count": row[2]} for row in accuracy_query.all()}

            for platform, total, resolved in stats:
                acc = accuracy_data.get(platform, {})
                avg_brier = acc.get("avg_brier")
                scored = acc.get("count", 0)

                reliability = 0.5
                if avg_brier is not None and scored >= 10:
                    reliability = max(0, 1 - avg_brier)

                record = SourceReliability(
                    platform=platform,
                    reliability_score=reliability,
                    accuracy_rate=1 - avg_brier if avg_brier else None,
                    sample_size=scored,
                    notes=f"Total items: {total}, Resolved: {resolved}, Scored predictions: {scored}",
                )
                db.add(record)
                actions.append(f"Updated reliability for {platform}: {reliability:.2f}")

            await db.commit()

        return {
            "summary": f"Computed reliability scores for {len(stats)} platforms",
            "actions": actions,
            "scratchpad_entries": [],
        }
