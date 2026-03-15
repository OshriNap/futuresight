"""Prediction generation — converts collected sources into scored predictions.

Uses the ToolRegistry to run prediction tools (market_consensus, ensemble, etc.)
and saves results as Prediction records.
"""

import json
import logging
from collections import Counter

from sqlalchemy import select

from app.database import async_session
from app.models.meta import PredictionMethod
from app.models.prediction import Prediction
from app.models.price_history import PriceSnapshot
from app.models.source import Source
from app.tools.base_tool import ToolInput
from app.tools.tool_registry import registry

logger = logging.getLogger(__name__)

# Polymarket slugs/titles containing these are low-value sports/entertainment
SPORTS_KEYWORDS = [
    "vs.", "o/u", "over/under", "total sets", "total kills", "total maps",
    "moneyline", "spread", "handicap", "game 1", "game 2", "game 3",
    "mvp", "assists", "rebounds", "touchdowns", "goals scored",
    "bachelorette", "bachelor", "survivor", "big brother",
]


def _is_sports_or_entertainment(title: str, slug: str | None) -> bool:
    lower = (title + " " + (slug or "")).lower()
    return any(kw in lower for kw in SPORTS_KEYWORDS)


async def generate_predictions() -> dict:
    """Generate predictions from market sources using the tool registry.

    Filters out sports/entertainment, runs tools on remaining markets,
    creates or updates Prediction records. Uses historical performance
    data to select and weight tools.
    """
    # Load performance data from scored predictions (feedback loop)
    from app.tasks.scoring_tasks import build_performance_data
    try:
        performance_data = await build_performance_data()
    except Exception:
        performance_data = None

    created = 0
    updated = 0
    skipped_sports = 0
    tool_usage = Counter()

    async with async_session() as db:
        # Get sources with actual market probabilities (not engagement/tone scores)
        result = await db.execute(
            select(Source)
            .where(Source.signal_type == "market_probability")
            .where(Source.current_market_probability.isnot(None))
        )
        sources = result.scalars().all()

        for source in sources:
            raw = source.raw_data or {}
            slug = raw.get("slug", "")

            # Skip sports/entertainment
            if _is_sports_or_entertainment(source.title, slug):
                skipped_sports += 1
                continue

            # Skip very low liquidity markets
            liquidity = raw.get("liquidityNum", 0) or raw.get("totalLiquidity", 0)
            if liquidity < 500:
                continue

            # Check if prediction already exists for this source
            existing = await db.execute(
                select(Prediction).where(Prediction.source_id == source.id)
            )
            pred = existing.scalar_one_or_none()

            # Parse outcomes
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

            # Build tool input
            signals = {
                "market_probability": source.current_market_probability,
                "market_volume": raw.get("volumeNum", 0) or raw.get("volume", 0),
                "bettor_count": raw.get("uniqueBettorCount", 0),
            }
            if len(prices) >= 2:
                signals["outcome_prices"] = {
                    outcomes[i]: float(prices[i])
                    for i in range(min(len(outcomes), len(prices)))
                }

            # Load price history for trend tools
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

            # Cross-reference with news sentiment (from GPU-analyzed sources)
            news_sentiment = await _get_news_sentiment(db, source)
            if news_sentiment is not None:
                signals["news_sentiment"] = news_sentiment

            # Pass embedding-matched sources for NLI tool
            matched_sources = raw.get("matched_sources", [])
            if matched_sources:
                signals["matched_sources"] = matched_sources

            # Cross-market: find same/similar questions on other platforms
            cross_market = await _find_cross_market(db, source)
            if cross_market:
                signals["market_probabilities"] = cross_market

            # Determine category from source
            category = source.category or _guess_category(source.title)

            # Determine time horizon from resolution date
            time_horizon = "medium"
            days_to_resolution = None
            if source.resolution_date:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                days_to_resolution = (source.resolution_date - now).days
                if days_to_resolution <= 7:
                    time_horizon = "short"
                elif days_to_resolution > 90:
                    time_horizon = "long"
                # Time decay: 0.0 (just opened) to 1.0 (resolving now)
                # Markets are better calibrated closer to resolution
                signals["time_decay"] = max(0.0, min(1.0, 1.0 - days_to_resolution / 365))

            tool_input = ToolInput(
                question=source.title,
                category=category,
                current_signals=signals,
                time_horizon=time_horizon,
                metadata={"source_id": source.id},
            )

            # Select and run tools (using performance feedback when available)
            tool_names = registry.select_tools(tool_input, performance_data)
            results = await registry.run_tools(tool_input, tool_names, performance_data)

            if not results:
                continue

            # Track tool usage
            for r in results:
                tool_usage[r.tool_name] += 1

            # Ensemble the results
            output = registry.ensemble_prediction(results)

            # Build data_signals with source info
            data_signals = output.metadata.get("data_signals", {})
            data_signals["sources"] = [{
                "name": source.title[:80],
                "platform": source.platform,
                "signal": f"Market probability: {source.current_market_probability:.1%}",
                "reliability": 0.5,
                "article_count": 1,
            }]

            if pred:
                # Update existing prediction
                pred.confidence = output.probability
                pred.reasoning = output.reasoning
                pred.data_signals = data_signals
                pred.predicted_outcome = "yes" if output.probability >= 0.5 else "no"
                updated += 1
            else:
                # Create new prediction
                pred = Prediction(
                    source_id=source.id,
                    prediction_text=source.title,
                    predicted_outcome="yes" if output.probability >= 0.5 else "no",
                    confidence=output.probability,
                    reasoning=output.reasoning,
                    time_horizon=time_horizon,
                    data_signals=data_signals,
                )
                db.add(pred)
                created += 1

        # Update PredictionMethod usage counts
        for tool_name, count in tool_usage.items():
            method_result = await db.execute(
                select(PredictionMethod).where(PredictionMethod.name == tool_name)
            )
            method = method_result.scalar_one_or_none()
            if method:
                method.total_uses += count

        await db.commit()

    logger.info(f"Predictions: created={created}, updated={updated}, skipped_sports={skipped_sports}")
    return {
        "created": created,
        "updated": updated,
        "skipped_sports": skipped_sports,
        "total_sources": len(sources),
    }


async def _find_cross_market(db, source: "Source") -> dict[str, float] | None:
    """Find the same or similar market on other platforms.

    Uses embedding-matched sources if available, otherwise keyword matching.
    Returns dict of {platform: probability} for the multi_market_ensemble tool.
    """
    import re

    # Extract key words from the question
    stop = {"will", "the", "be", "by", "on", "in", "at", "to", "for", "of", "is",
            "are", "and", "or", "a", "an", "this", "that", "from", "with", "has", "its",
            "before", "after", "more", "than", "about"}
    words = [w for w in re.findall(r'[a-z]+', source.title.lower()) if w not in stop and len(w) > 3]
    if len(words) < 2:
        return None

    # Search for markets on other platforms with overlapping keywords
    from sqlalchemy import and_, or_
    search_words = words[:4]
    conditions = [Source.title.ilike(f"%{w}%") for w in search_words]

    result = await db.execute(
        select(Source)
        .where(Source.signal_type == "market_probability")
        .where(Source.platform != source.platform)
        .where(Source.current_market_probability.isnot(None))
        .where(or_(*conditions))
        .limit(10)
    )
    candidates = result.scalars().all()

    if not candidates:
        return None

    # Score candidates by keyword overlap
    best_match = None
    best_score = 0
    source_words = set(words)
    for c in candidates:
        c_words = set(w for w in re.findall(r'[a-z]+', c.title.lower()) if w not in stop and len(w) > 3)
        overlap = len(source_words & c_words)
        if overlap > best_score and overlap >= 3:  # require 3+ word overlap
            best_score = overlap
            best_match = c

    if not best_match:
        return None

    probs = {source.platform: source.current_market_probability}
    probs[best_match.platform] = best_match.current_market_probability
    return probs


async def _get_news_sentiment(db, source: "Source") -> float | None:
    """Get aggregated sentiment from matched news sources.

    First checks for embedding-matched sources (from match_sources task),
    then falls back to keyword matching. Returns sentiment in [-1, 1] range.
    """
    raw = source.raw_data or {}

    # Prefer embedding matches (higher quality)
    matched = raw.get("matched_sources", [])
    if matched:
        sentiments = [m["sentiment"] for m in matched if m.get("sentiment") is not None]
        if sentiments:
            # Weight by similarity score
            weights = [m.get("similarity", 1.0) for m in matched if m.get("sentiment") is not None]
            return sum(s * w for s, w in zip(sentiments, weights)) / sum(weights)

    # Fallback: keyword matching
    import re
    title = source.title
    stop = {"will", "the", "be", "by", "on", "in", "at", "to", "for", "of", "is",
            "are", "and", "or", "a", "an", "this", "that", "from", "with", "has", "its"}
    words = [w for w in re.findall(r'[a-z]+', title.lower()) if w not in stop and len(w) > 3]

    if not words:
        return None

    search_words = words[:3]

    from sqlalchemy import or_
    conditions = [Source.title.ilike(f"%{w}%") for w in search_words]
    result = await db.execute(
        select(Source)
        .where(Source.platform.in_(["gdelt", "reddit"]))
        .where(or_(*conditions))
        .limit(20)
    )
    matching_news = result.scalars().all()

    if not matching_news:
        return None

    sentiments = []
    for news in matching_news:
        nraw = news.raw_data or {}
        sentiment = nraw.get("sentiment")
        if sentiment is not None:
            sentiments.append(sentiment)

    if not sentiments:
        return None

    return sum(sentiments) / len(sentiments)


def _guess_category(title: str) -> str:
    """Guess category from title keywords."""
    lower = title.lower()
    if any(w in lower for w in ["bitcoin", "ethereum", "crypto", "market cap", "stock", "ipo", "price"]):
        return "finance"
    if any(w in lower for w in ["election", "vote", "president", "senate", "governor", "nominee", "democrat", "republican"]):
        return "politics"
    if any(w in lower for w in ["war", "invasion", "sanction", "military", "nato", "nuclear"]):
        return "geopolitics"
    if any(w in lower for w in ["ai", "openai", "google", "apple", "tech", "software"]):
        return "technology"
    if any(w in lower for w in ["climate", "temperature", "weather", "hurricane", "earthquake"]):
        return "climate"
    if any(w in lower for w in ["covid", "vaccine", "health", "disease", "measles", "pandemic"]):
        return "health"
    if any(w in lower for w in ["gdp", "inflation", "fed", "interest rate", "recession", "economy"]):
        return "economy"
    return "general"
