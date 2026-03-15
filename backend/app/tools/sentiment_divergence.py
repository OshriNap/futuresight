"""Sentiment Divergence Tool

Detects when market probability and news sentiment disagree.
When the market says 90% but news sentiment is negative, that's a strong
contrarian signal — the market may be ignoring negative information.

From backtesting: worst predictions often have this pattern.
"""

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput


class SentimentDivergenceTool(BasePredictionTool):
    name = "sentiment_divergence"
    tool_type = "heuristic"
    description = (
        "Detects market-sentiment disagreement. When market is bullish but news "
        "is bearish (or vice versa), applies a contrarian correction."
    )
    best_for = ["technology", "geopolitics", "economy", "politics", "finance"]

    async def predict(self, input: ToolInput) -> ToolOutput:
        market_prob = input.current_signals.get("market_probability", 0.5)
        sentiment = input.current_signals.get("news_sentiment")

        if sentiment is None:
            return ToolOutput(
                probability=market_prob,
                confidence=0.1,
                reasoning="No news sentiment available for divergence check",
                signals_used=["market_probability"],
            )

        # Market direction: >0.5 = bullish (YES), <0.5 = bearish (NO)
        market_direction = market_prob - 0.5  # [-0.5, 0.5]
        # Sentiment: [-1, 1] where positive = good news

        # Divergence: market is bullish but sentiment is negative, or vice versa
        # Normalize both to [-1, 1] range
        market_signal = market_direction * 2  # [-1, 1]
        divergence = market_signal - sentiment  # high = market bullish + sentiment bearish

        # Only act on meaningful divergence
        if abs(divergence) < 0.3:
            return ToolOutput(
                probability=market_prob,
                confidence=0.15,
                reasoning=f"No significant market-sentiment divergence (div={divergence:+.2f})",
                signals_used=["market_probability", "news_sentiment"],
            )

        # Apply correction: push probability toward where sentiment suggests
        # Scale: max ±8% adjustment for strong divergence
        correction = -divergence * 0.04  # negative divergence = sentiment says "too bullish"
        adjusted = max(0.02, min(0.98, market_prob + correction))

        confidence = min(0.5, 0.2 + abs(divergence) * 0.2)
        direction = "bearish" if correction < 0 else "bullish"

        reasoning = (
            f"Sentiment divergence detected: market={market_prob:.1%} ({market_signal:+.2f}) "
            f"vs sentiment={sentiment:+.2f}, divergence={divergence:+.2f}. "
            f"Correction: {correction:+.1%} ({direction}). "
            f"Adjusted: {adjusted:.1%}"
        )

        return ToolOutput(
            probability=adjusted,
            confidence=confidence,
            reasoning=reasoning,
            signals_used=["market_probability", "news_sentiment"],
            metadata={
                "divergence": round(divergence, 3),
                "correction": round(correction, 4),
                "sentiment": round(sentiment, 3),
            },
        )

    def get_required_signals(self) -> list[str]:
        return ["market_probability", "news_sentiment"]
