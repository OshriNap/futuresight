"""Advanced Extrapolation Toolkit

Multiple extrapolation methods beyond simple linear regression.
Each method has different assumptions and is better for different scenarios.
The system learns which extrapolation method works best for which category.
"""

import math
from dataclasses import dataclass

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput


@dataclass
class ExtrapolationResult:
    method: str
    predicted_value: float
    confidence: float
    reasoning: str
    fit_quality: float  # 0-1, how well the method fits historical data


def linear_extrapolation(values: list[float], steps_ahead: int = 1) -> ExtrapolationResult:
    """Simple linear regression extrapolation."""
    n = len(values)
    if n < 2:
        return ExtrapolationResult("linear", values[-1] if values else 0.5, 0.1, "Too few points", 0)

    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den > 0 else 0
    intercept = y_mean - slope * x_mean

    predicted = intercept + slope * (n - 1 + steps_ahead)
    predicted = max(0.01, min(0.99, predicted))

    # R²
    ss_res = sum((v - (intercept + slope * i)) ** 2 for i, v in enumerate(values))
    ss_tot = sum((v - y_mean) ** 2 for v in values)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    return ExtrapolationResult(
        "linear", predicted, max(0.1, r2 * 0.7),
        f"Linear trend: slope={slope:+.4f}, R²={r2:.3f}", r2
    )


def exponential_smoothing(values: list[float], alpha: float = 0.3) -> ExtrapolationResult:
    """Simple exponential smoothing (SES).

    Recent values get more weight. Good for noisy data without strong trend.
    Alpha controls how much weight to give recent observations.
    """
    if not values:
        return ExtrapolationResult("exp_smoothing", 0.5, 0.1, "No data", 0)

    smoothed = values[0]
    for v in values[1:]:
        smoothed = alpha * v + (1 - alpha) * smoothed

    predicted = max(0.01, min(0.99, smoothed))

    # Fit quality: compare smoothed values to actual
    fit_errors = []
    s = values[0]
    for v in values[1:]:
        fit_errors.append((v - s) ** 2)
        s = alpha * v + (1 - alpha) * s
    mse = sum(fit_errors) / len(fit_errors) if fit_errors else 1
    fit = max(0, 1 - mse * 4)  # Normalize

    return ExtrapolationResult(
        "exp_smoothing", predicted, max(0.15, fit * 0.6),
        f"Exponential smoothing (α={alpha}): next={predicted:.3f}", fit
    )


def double_exponential(values: list[float], alpha: float = 0.3, beta: float = 0.1) -> ExtrapolationResult:
    """Holt's double exponential smoothing.

    Handles both level AND trend. Better for data with consistent trends.
    """
    if len(values) < 2:
        return ExtrapolationResult("double_exp", values[-1] if values else 0.5, 0.1, "Need 2+ points", 0)

    level = values[0]
    trend = values[1] - values[0]

    for v in values[1:]:
        prev_level = level
        level = alpha * v + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend

    predicted = level + trend
    predicted = max(0.01, min(0.99, predicted))

    return ExtrapolationResult(
        "double_exp", predicted, 0.4,
        f"Holt's method: level={level:.3f}, trend={trend:+.4f}, next={predicted:.3f}", 0.5
    )


def moving_average_forecast(values: list[float], window: int = 5) -> ExtrapolationResult:
    """Weighted moving average with more recent values weighted higher."""
    if not values:
        return ExtrapolationResult("weighted_ma", 0.5, 0.1, "No data", 0)

    w = min(window, len(values))
    recent = values[-w:]
    weights = list(range(1, w + 1))  # Linear weights: 1, 2, 3, ...
    total_weight = sum(weights)
    predicted = sum(v * wt for v, wt in zip(recent, weights)) / total_weight
    predicted = max(0.01, min(0.99, predicted))

    return ExtrapolationResult(
        "weighted_ma", predicted, 0.35,
        f"Weighted MA({w}): {predicted:.3f}", 0.4
    )


def mean_reversion(values: list[float], reversion_speed: float = 0.3) -> ExtrapolationResult:
    """Mean reversion model.

    Assumes values tend to revert to their long-term average.
    Good for markets and probabilities that overshoot.
    """
    if not values:
        return ExtrapolationResult("mean_reversion", 0.5, 0.1, "No data", 0)

    long_term_mean = sum(values) / len(values)
    current = values[-1]

    # Predict reversion toward mean
    predicted = current + reversion_speed * (long_term_mean - current)
    predicted = max(0.01, min(0.99, predicted))

    deviation = abs(current - long_term_mean)
    confidence = min(0.6, 0.2 + deviation * 0.5)  # More confident when far from mean

    return ExtrapolationResult(
        "mean_reversion", predicted, confidence,
        f"Mean reversion: current={current:.3f}, mean={long_term_mean:.3f}, "
        f"predicted={predicted:.3f} (speed={reversion_speed})", 0.5
    )


def ensemble_extrapolation(values: list[float]) -> ExtrapolationResult:
    """Ensemble of all extrapolation methods.

    Weights methods by their fit quality on historical data.
    """
    if len(values) < 3:
        return linear_extrapolation(values)

    methods = [
        linear_extrapolation(values),
        exponential_smoothing(values, alpha=0.3),
        double_exponential(values),
        moving_average_forecast(values),
        mean_reversion(values),
    ]

    # Weight by fit quality
    total_weight = sum(max(0.1, m.fit_quality) for m in methods)
    weighted_pred = sum(m.predicted_value * max(0.1, m.fit_quality) for m in methods) / total_weight

    weighted_pred = max(0.01, min(0.99, weighted_pred))
    best_method = max(methods, key=lambda m: m.fit_quality)

    return ExtrapolationResult(
        "ensemble", weighted_pred,
        confidence=min(0.7, max(m.confidence for m in methods)),
        reasoning=f"Ensemble of {len(methods)} methods. Best fit: {best_method.method} "
                  f"(quality={best_method.fit_quality:.2f}). "
                  f"Range: [{min(m.predicted_value for m in methods):.3f}, "
                  f"{max(m.predicted_value for m in methods):.3f}]",
        fit_quality=max(m.fit_quality for m in methods),
    )


class AdvancedExtrapolatorTool(BasePredictionTool):
    """Prediction tool that uses ensemble extrapolation with method selection."""

    name = "advanced_extrapolation"
    tool_type = "statistical"
    description = "Ensemble of extrapolation methods (linear, exponential smoothing, Holt's, MA, mean reversion)."
    best_for = ["economics", "markets", "tech"]

    async def predict(self, input: ToolInput) -> ToolOutput:
        history = input.current_signals.get("probability_history", [])
        values = [h["probability"] for h in history] if history else []

        if len(values) < 2:
            fallback = input.current_signals.get("market_probability", 0.5)
            return ToolOutput(
                probability=fallback, confidence=0.15,
                reasoning="Insufficient history for extrapolation",
                signals_used=["market_probability"] if "market_probability" in input.current_signals else [],
            )

        result = ensemble_extrapolation(values)

        return ToolOutput(
            probability=result.predicted_value,
            confidence=result.confidence,
            reasoning=result.reasoning,
            signals_used=["probability_history"],
            metadata={"method": result.method, "fit_quality": result.fit_quality},
        )

    def get_required_signals(self) -> list[str]:
        return ["probability_history"]
