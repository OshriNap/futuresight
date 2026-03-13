"""Source Evaluator Meta-Agent

Periodically reviews all data sources, evaluates their reliability,
and recommends adding/removing/adjusting source weights.

Responsibilities:
- Calculate accuracy rates per source platform
- Evaluate timeliness (how quickly sources report events)
- Track coverage (breadth of topics)
- Compare sources against each other
- Suggest new sources to add
- Flag sources that have degraded in quality
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
        """Evaluate all sources and update reliability scores."""
        entries = []
        actions = []

        async with async_session() as db:
            # Get per-platform stats
            platform_stats = await db.execute(
                select(
                    Source.platform,
                    func.count(Source.id).label("total"),
                    func.count(Source.resolved_at).label("resolved"),
                )
                .group_by(Source.platform)
            )
            stats = platform_stats.all()

            # Get prediction accuracy per source platform
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

                # Calculate reliability score (composite)
                reliability = 0.5  # default
                if avg_brier is not None and scored >= 10:
                    # Lower brier = better (0 is perfect, 1 is worst)
                    reliability = max(0, 1 - avg_brier)

                # Save reliability record
                record = SourceReliability(
                    platform=platform,
                    reliability_score=reliability,
                    accuracy_rate=1 - avg_brier if avg_brier else None,
                    sample_size=scored,
                    notes=f"Total items: {total}, Resolved: {resolved}, Scored predictions: {scored}",
                )
                db.add(record)

                # Generate insights
                if avg_brier is not None and avg_brier > 0.4:
                    entries.append({
                        "title": f"Low reliability detected: {platform}",
                        "content": f"Platform {platform} has avg Brier score of {avg_brier:.3f} "
                                   f"across {scored} predictions. Consider reducing weight or investigating.",
                        "category": "insight",
                        "priority": "high",
                        "tags": ["source_quality", platform],
                    })
                    actions.append(f"Flagged {platform} as low reliability (Brier: {avg_brier:.3f})")

                if total > 0 and resolved / total < 0.1 and total > 50:
                    entries.append({
                        "title": f"Low resolution rate: {platform}",
                        "content": f"Only {resolved}/{total} ({resolved/total*100:.1f}%) items from {platform} "
                                   f"have been resolved. May need better resolution tracking.",
                        "category": "insight",
                        "tags": ["resolution", platform],
                    })

            await db.commit()

        # Always think about new sources
        entries.append({
            "title": "Periodic source review completed",
            "content": f"Evaluated {len(stats)} platforms. "
                       "Consider investigating: financial data (FRED API), social media sentiment, "
                       "academic preprints (arXiv), government data releases, satellite imagery trends.",
            "category": "idea",
            "priority": "low",
            "tags": ["source_expansion"],
        })

        return {
            "summary": f"Evaluated {len(stats)} source platforms, generated {len(entries)} insights",
            "actions": actions,
            "scratchpad_entries": entries,
        }
