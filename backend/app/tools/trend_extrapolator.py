"""Trend Extrapolation Tool

Analyzes probability time series and extrapolates trends.
Uses simple statistical methods (linear regression, moving averages).
"""

import math

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput


class TrendExtrapolatorTool(BasePredictionTool):
    name = "trend_extrapolation"
    tool_type = "statistical"
    description = "Extrapolates probability trends from time-series data using regression."
    best_for = ["economics", "tech", "markets"]
    requires_training = False

    async def predict(self, input: ToolInput) -> ToolOutput:
        history = input.current_signals.get("probability_history", [])
        # Expected: [{"timestamp": "...", "probability": 0.65}, ...]

        if len(history) < 3:
            return ToolOutput(
                probability=history[-1]["probability"] if history else 0.5,
                confidence=0.2,
                reasoning="Insufficient history for trend analysis (need 3+ data points)",
                signals_used=["probability_history"] if history else [],
            )

        probs = [h["probability"] for h in history]
        n = len(probs)

        # Simple linear regression
        x_mean = (n - 1) / 2
        y_mean = sum(probs) / n
        numerator = sum((i - x_mean) * (p - y_mean) for i, p in enumerate(probs))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator

        intercept = y_mean - slope * x_mean

        # Extrapolate next step
        next_prob = intercept + slope * n
        next_prob = max(0.01, min(0.99, next_prob))  # Clamp to valid range

        # Calculate R² for confidence
        ss_res = sum((p - (intercept + slope * i)) ** 2 for i, p in enumerate(probs))
        ss_tot = sum((p - y_mean) ** 2 for p in probs)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Moving average for comparison
        window = min(5, n)
        ma = sum(probs[-window:]) / window

        # Confidence based on R², data points, and agreement between methods
        confidence = max(0.15, min(0.75, r_squared * 0.5 + (n / 50) * 0.3))

        trend_dir = "upward" if slope > 0.01 else "downward" if slope < -0.01 else "flat"

        return ToolOutput(
            probability=next_prob,
            confidence=confidence,
            reasoning=f"Trend: {trend_dir} (slope: {slope:+.4f}/step). "
                      f"Linear extrapolation: {next_prob:.1%}, MA({window}): {ma:.1%}. "
                      f"R²={r_squared:.3f} over {n} data points.",
            signals_used=["probability_history"],
            metadata={"slope": slope, "r_squared": r_squared, "moving_average": ma},
        )

    def get_required_signals(self) -> list[str]:
        return ["probability_history"]
