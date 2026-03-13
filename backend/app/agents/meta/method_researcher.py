"""Method Researcher Meta-Agent

Thinks about and evaluates different prediction methodologies.

Responsibilities:
- Track which prediction methods are available (statistical, ML, LLM reasoning, etc.)
- Evaluate method performance per category
- Research new methods and approaches
- Manage feature importance tracking
- Suggest method improvements and new feature engineering ideas
"""

import logging

from sqlalchemy import func, select

from app.agents.meta.base_meta import BaseMetaAgent
from app.database import async_session
from app.models.meta import FeatureImportance, PredictionMethod

logger = logging.getLogger(__name__)

# Registry of known prediction approaches to consider
KNOWN_METHODS = [
    {
        "name": "market_consensus",
        "type": "heuristic",
        "description": "Use prediction market probabilities directly as forecasts. Simple baseline.",
    },
    {
        "name": "multi_market_ensemble",
        "type": "ensemble",
        "description": "Weighted average of probabilities from multiple prediction markets (Polymarket, Manifold, etc.)",
    },
    {
        "name": "llm_reasoning",
        "type": "llm_reasoning",
        "description": "Use Claude to reason about events given context from news and market data.",
    },
    {
        "name": "trend_extrapolation",
        "type": "statistical",
        "description": "Track probability trends over time and extrapolate using time-series methods.",
    },
    {
        "name": "news_sentiment_signal",
        "type": "ml_model",
        "description": "Aggregate news sentiment as a signal for probability direction changes.",
    },
    {
        "name": "base_rate_adjustment",
        "type": "statistical",
        "description": "Adjust predictions based on historical base rates for similar event categories.",
    },
    {
        "name": "superforecaster_aggregation",
        "type": "ensemble",
        "description": "Weight forecasts by each method's historical accuracy (Brier score) per category.",
    },
    {
        "name": "causal_graph_propagation",
        "type": "heuristic",
        "description": "Use the event causality graph to propagate probability changes through related events.",
    },
]

# Known useful features for predictions
KNOWN_FEATURES = [
    {"name": "market_probability", "source": "prediction_markets", "description": "Current market price/probability"},
    {"name": "market_volume", "source": "prediction_markets", "description": "Trading volume as liquidity/attention signal"},
    {"name": "probability_momentum", "source": "derived", "description": "Rate of probability change over time"},
    {"name": "news_volume", "source": "news", "description": "Number of related news articles recently"},
    {"name": "news_sentiment", "source": "news", "description": "Aggregate sentiment of related news"},
    {"name": "source_agreement", "source": "derived", "description": "How much different sources agree on probability"},
    {"name": "time_to_resolution", "source": "derived", "description": "Days until expected resolution date"},
    {"name": "category_base_rate", "source": "historical", "description": "Historical resolution rate for this category"},
    {"name": "graph_connectivity", "source": "event_graph", "description": "How connected this event is to other events"},
    {"name": "cascade_exposure", "source": "event_graph", "description": "Probability shift from related event resolutions"},
]


class MethodResearcher(BaseMetaAgent):
    agent_type = "method_researcher"

    async def think(self) -> dict:
        entries = []
        actions = []

        async with async_session() as db:
            # Ensure all known methods are registered
            for method_info in KNOWN_METHODS:
                existing = await db.execute(
                    select(PredictionMethod).where(PredictionMethod.name == method_info["name"])
                )
                if not existing.scalar_one_or_none():
                    method = PredictionMethod(
                        name=method_info["name"],
                        method_type=method_info["type"],
                        description=method_info["description"],
                    )
                    db.add(method)
                    actions.append(f"Registered method: {method_info['name']}")

            # Get performance data for active methods
            methods_result = await db.execute(
                select(PredictionMethod)
                .where(PredictionMethod.is_active == True)
                .order_by(PredictionMethod.avg_accuracy.desc().nullslast())
            )
            active_methods = methods_result.scalars().all()

            # Analyze which methods have enough data
            untested = [m for m in active_methods if m.total_uses < 10]
            if untested:
                entries.append({
                    "title": f"{len(untested)} methods need more testing",
                    "content": "The following methods have fewer than 10 uses and need more data: "
                               + ", ".join(m.name for m in untested)
                               + ". Consider running A/B tests or allocating prediction quota.",
                    "category": "todo",
                    "priority": "medium",
                    "tags": ["method_testing", "experiment"],
                })

            # Check for methods that consistently underperform
            poor_methods = [m for m in active_methods if m.avg_accuracy is not None and m.avg_accuracy < 0.3 and m.total_uses >= 20]
            for m in poor_methods:
                entries.append({
                    "title": f"Method underperforming: {m.name}",
                    "content": f"{m.name} has {m.avg_accuracy:.1%} accuracy across {m.total_uses} uses. "
                               f"Best categories: {m.best_categories}, Worst: {m.worst_categories}. "
                               f"Consider deactivating or restricting to best categories only.",
                    "category": "insight",
                    "priority": "high",
                    "tags": ["method_quality", m.name],
                })

            # Feature importance analysis ideas
            entries.append({
                "title": "Feature engineering review",
                "content": "Current known features: " + ", ".join(f["name"] for f in KNOWN_FEATURES)
                           + "\n\nPotential new features to explore:\n"
                           "- Social media mention velocity\n"
                           "- Expert vs crowd disagreement score\n"
                           "- Event recurrence patterns (has this type of event happened before?)\n"
                           "- Geographic proximity signals\n"
                           "- Economic indicator correlations\n"
                           "- Seasonal patterns for certain event types",
                "category": "idea",
                "priority": "medium",
                "tags": ["features", "research"],
            })

            await db.commit()

        return {
            "summary": f"Reviewed {len(active_methods)} methods, {len(entries)} insights generated",
            "actions": actions,
            "scratchpad_entries": entries,
        }
