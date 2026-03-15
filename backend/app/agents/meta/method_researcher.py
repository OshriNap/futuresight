"""Method Researcher Meta-Agent

DB-only operations: ensures prediction methods are registered.
All analytical thinking is handled by Claude Code scheduled tasks.
"""

import logging

from sqlalchemy import select

from app.agents.meta.base_meta import BaseMetaAgent
from app.database import async_session
from app.models.meta import PredictionMethod

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
        """Ensure methods are registered in DB. Analysis is Claude Code's job."""
        actions = []

        async with async_session() as db:
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

            await db.commit()

        return {
            "summary": f"Ensured {len(KNOWN_METHODS)} methods are registered in DB",
            "actions": actions,
            "scratchpad_entries": [],
        }
