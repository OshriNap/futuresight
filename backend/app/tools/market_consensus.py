"""Market Consensus Tool

The simplest prediction method: use the prediction market's probability directly.
Acts as a strong baseline that more complex methods should beat.
"""

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput


class MarketConsensusTool(BasePredictionTool):
    name = "market_consensus"
    tool_type = "heuristic"
    description = "Uses prediction market probability as the forecast. Strong baseline."
    best_for = ["politics", "sports", "events"]

    async def predict(self, input: ToolInput) -> ToolOutput:
        market_prob = input.current_signals.get("market_probability")
        if market_prob is None:
            return ToolOutput(
                probability=0.5,
                confidence=0.1,
                reasoning="No market probability available, defaulting to 50%",
                signals_used=[],
            )

        # Market probability is the prediction
        # Confidence scales with market volume (more volume = more confident in market)
        volume = input.current_signals.get("market_volume", 0)
        confidence = min(0.9, 0.3 + (volume / 1_000_000) * 0.6) if volume > 0 else 0.5

        return ToolOutput(
            probability=float(market_prob),
            confidence=confidence,
            reasoning=f"Using market consensus probability of {market_prob:.1%} "
                      f"(volume: ${volume:,.0f})",
            signals_used=["market_probability", "market_volume"],
        )

    def get_required_signals(self) -> list[str]:
        return ["market_probability"]
