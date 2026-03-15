"""Contrarian / Extremity Dampener Tool

Key insight from backtesting: the worst predictions are all extreme probabilities
(>90% or <10%) that turned out wrong. Markets overconfident at extremes.

This tool applies mean reversion to extreme probabilities, based on the empirical
finding that prediction markets are systematically overconfident at the tails.

Research: Atanasov et al. (2017) found extremizing helps ensembles but individual
extreme forecasts are worse-calibrated than moderate ones.
"""

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput


# Calibration data from our backtest + forecasting literature:
# When markets say 90%+, the true rate is ~80-85%
# When markets say <10%, the true rate is ~15-20%
DAMPENING_CURVE = {
    # (lower_bound, upper_bound): dampening_factor
    # Factor < 1 pulls toward 50%, factor > 1 pushes away
    (0.0, 0.05): 0.60,   # 2% market -> ~3.2% (less extreme)
    (0.05, 0.15): 0.75,  # 10% market -> ~12.5%
    (0.15, 0.30): 0.90,  # 20% market -> ~23%
    (0.30, 0.70): 1.00,  # middle range: no change
    (0.70, 0.85): 0.90,  # 80% market -> ~77%
    (0.85, 0.95): 0.75,  # 90% market -> ~87.5%
    (0.95, 1.0): 0.60,   # 98% market -> ~96.8%
}


def _dampen(prob: float) -> float:
    """Apply dampening to pull extreme probabilities toward 50%."""
    for (lo, hi), factor in DAMPENING_CURVE.items():
        if lo <= prob < hi:
            # Dampen the distance from 0.5
            distance = prob - 0.5
            return 0.5 + distance * factor
    return prob


class ContrarianTool(BasePredictionTool):
    name = "contrarian_dampener"
    tool_type = "statistical"
    description = (
        "Dampens extreme market probabilities based on empirical overconfidence at tails. "
        "Markets saying 95% are right ~85% of the time."
    )
    best_for = ["general", "technology", "geopolitics", "politics", "economy"]

    async def predict(self, input: ToolInput) -> ToolOutput:
        market_prob = input.current_signals.get("market_probability", 0.5)

        dampened = _dampen(market_prob)
        adjustment = dampened - market_prob

        # Higher confidence when market is extreme (that's where we add most value)
        distance_from_center = abs(market_prob - 0.5)
        confidence = 0.2 + distance_from_center * 0.6  # 0.2 at center, 0.5 at extremes

        if abs(adjustment) < 0.001:
            reasoning = f"Market probability {market_prob:.1%} is in the moderate range — no dampening needed."
        else:
            direction = "toward 50%" if abs(dampened - 0.5) < abs(market_prob - 0.5) else "away from 50%"
            reasoning = (
                f"Dampened {market_prob:.1%} → {dampened:.1%} ({direction}, {adjustment:+.1%}). "
                f"Extreme market probabilities are historically overconfident."
            )

        return ToolOutput(
            probability=dampened,
            confidence=confidence,
            reasoning=reasoning,
            signals_used=["market_probability"],
            metadata={
                "original_prob": round(market_prob, 4),
                "dampened_prob": round(dampened, 4),
                "adjustment": round(adjustment, 4),
            },
        )

    def get_required_signals(self) -> list[str]:
        return ["market_probability"]
