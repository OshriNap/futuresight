"""Base Rate Adjustment Tool

Uses historical base rates for similar event categories to adjust predictions.
A key insight from forecasting research: most people ignore base rates.
"""

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput

# Default base rates by category (can be updated from historical data)
DEFAULT_BASE_RATES = {
    "geopolitical": {
        "conflict_escalation": 0.25,
        "treaty_signed": 0.15,
        "election_incumbent_wins": 0.55,
        "sanctions_imposed": 0.40,
    },
    "economic": {
        "recession": 0.15,
        "rate_hike": 0.50,
        "market_crash_10pct": 0.08,
        "startup_success": 0.10,
    },
    "tech": {
        "product_launches_on_time": 0.35,
        "regulation_passes": 0.30,
        "acquisition_completes": 0.70,
    },
    "social": {
        "protest_leads_to_change": 0.20,
        "pandemic_declaration": 0.05,
    },
    "environmental": {
        "climate_target_met": 0.15,
        "natural_disaster_major": 0.10,
    },
}


class BaseRateTool(BasePredictionTool):
    name = "base_rate_adjustment"
    tool_type = "statistical"
    description = "Adjusts predictions using historical base rates for similar events."
    best_for = ["geopolitical", "economic"]

    async def predict(self, input: ToolInput) -> ToolOutput:
        category = input.category
        current_prob = input.current_signals.get("market_probability", 0.5)

        # Look up base rate
        base_rates = DEFAULT_BASE_RATES.get(category, {})
        subcategory = input.current_signals.get("subcategory", "")

        base_rate = base_rates.get(subcategory)

        # Also check historical data
        if input.historical_data and len(input.historical_data) >= 5:
            historical_rate = sum(
                1 for h in input.historical_data if h.get("actual_outcome") == "yes"
            ) / len(input.historical_data)
            base_rate = historical_rate  # Prefer empirical base rate

        if base_rate is None:
            return ToolOutput(
                probability=current_prob,
                confidence=0.2,
                reasoning=f"No base rate found for category '{category}'. Using market probability.",
                signals_used=["market_probability"],
            )

        # Bayesian-like adjustment: weight between base rate and current estimate
        # The more data we have, the more we trust current signals over base rate
        data_strength = min(1.0, len(input.historical_data or []) / 50)
        adjusted = base_rate * (1 - data_strength) + current_prob * data_strength

        return ToolOutput(
            probability=adjusted,
            confidence=0.4 + data_strength * 0.3,
            reasoning=f"Base rate for {category}/{subcategory}: {base_rate:.1%}. "
                      f"Current signal: {current_prob:.1%}. "
                      f"Adjusted (data strength {data_strength:.1%}): {adjusted:.1%}",
            signals_used=["market_probability", "subcategory"],
            metadata={"base_rate": base_rate, "data_strength": data_strength},
        )

    def get_required_signals(self) -> list[str]:
        return []  # Can work with minimal input
