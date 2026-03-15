"""Base Rate Adjustment Tool

Uses category-level base rates to anchor predictions. The key insight from
forecasting research: most people ignore base rates (base rate neglect).

Anchors toward the category's empirical YES-resolution rate, weighted by
how much data we have. Categories where markets are less efficient get
stronger base rate anchoring.
"""

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput

# Empirical base rates: fraction of markets that resolve YES by category.
# Derived from backtesting against resolved Manifold markets.
# Also includes "market efficiency" — how well-calibrated markets are in this category.
CATEGORY_RATES = {
    # category: (yes_rate, market_efficiency)
    # efficiency < 1.0 means markets are less reliable → anchor to base rate more
    "politics": (0.42, 0.85),
    "geopolitics": (0.38, 0.80),
    "technology": (0.35, 0.75),   # markets often overhype tech claims
    "economy": (0.40, 0.82),
    "finance": (0.45, 0.80),
    "climate": (0.30, 0.70),
    "health": (0.35, 0.75),
    "general": (0.40, 0.80),
}

# How much to weight the base rate vs market probability
# Higher = trust base rate more (0 = ignore base rate, 1 = ignore market)
BASE_RATE_WEIGHT = 0.15


class BaseRateTool(BasePredictionTool):
    name = "base_rate_adjustment"
    tool_type = "statistical"
    description = "Anchors predictions toward category base rates. Corrects for base rate neglect."
    best_for = ["geopolitical", "economic", "technology", "general"]

    async def predict(self, input: ToolInput) -> ToolOutput:
        category = input.category
        current_prob = input.current_signals.get("market_probability", 0.5)

        # Get category base rate
        yes_rate, efficiency = CATEGORY_RATES.get(category, (0.40, 0.80))

        # Weight between base rate and market: less efficient categories get
        # stronger anchoring toward the base rate
        anchor_weight = BASE_RATE_WEIGHT * (1 - efficiency + 0.2)
        adjusted = current_prob * (1 - anchor_weight) + yes_rate * anchor_weight

        # Clamp
        adjusted = max(0.02, min(0.98, adjusted))

        shift = adjusted - current_prob
        confidence = 0.3 + (1 - efficiency) * 0.3  # higher confidence for less efficient categories

        reasoning = (
            f"Category '{category}' base rate: {yes_rate:.0%} YES "
            f"(market efficiency: {efficiency:.0%}). "
            f"Anchored {current_prob:.1%} → {adjusted:.1%} ({shift:+.1%})."
        )

        return ToolOutput(
            probability=adjusted,
            confidence=confidence,
            reasoning=reasoning,
            signals_used=["market_probability"],
            metadata={
                "category": category,
                "base_rate": yes_rate,
                "market_efficiency": efficiency,
                "anchor_weight": round(anchor_weight, 3),
            },
        )

    def get_required_signals(self) -> list[str]:
        return ["market_probability"]
