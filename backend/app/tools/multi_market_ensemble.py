"""Multi-Market Ensemble Tool

Combines probabilities from multiple prediction markets using weighted averaging.
Weights are based on each market's historical reliability score.
"""

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput


class MultiMarketEnsembleTool(BasePredictionTool):
    name = "multi_market_ensemble"
    tool_type = "ensemble"
    description = "Weighted average of probabilities from multiple prediction markets."
    best_for = ["politics", "economics", "events"]

    async def predict(self, input: ToolInput) -> ToolOutput:
        market_probs = input.current_signals.get("market_probabilities", {})
        # Expected format: {"polymarket": 0.65, "manifold": 0.70, "predictit": 0.60}

        if not market_probs:
            return ToolOutput(
                probability=0.5,
                confidence=0.1,
                reasoning="No multi-market data available",
                signals_used=[],
            )

        # Get reliability weights (default equal weights)
        reliability = input.current_signals.get("source_reliability", {})
        total_weight = 0
        weighted_sum = 0

        details = []
        for market, prob in market_probs.items():
            weight = reliability.get(market, 1.0)
            weighted_sum += prob * weight
            total_weight += weight
            details.append(f"{market}: {prob:.1%} (weight: {weight:.2f})")

        probability = weighted_sum / total_weight if total_weight > 0 else 0.5

        # Confidence based on agreement between markets
        probs = list(market_probs.values())
        spread = max(probs) - min(probs) if len(probs) > 1 else 0
        agreement_confidence = max(0.2, 1.0 - spread * 2)  # High spread = low confidence
        confidence = min(0.9, agreement_confidence * (0.5 + len(probs) * 0.1))

        return ToolOutput(
            probability=probability,
            confidence=confidence,
            reasoning=f"Ensemble of {len(market_probs)} markets: {', '.join(details)}. "
                      f"Spread: {spread:.1%}, Agreement confidence: {agreement_confidence:.1%}",
            signals_used=["market_probabilities", "source_reliability"],
        )

    def get_required_signals(self) -> list[str]:
        return ["market_probabilities"]
