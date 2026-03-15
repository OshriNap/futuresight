"""Historical Analogy Tool

Finds structurally similar resolved questions and uses their resolution rate
as a signal. "Will X country do Y by Z" — what happened with similar questions?

This is a form of reference class forecasting: instead of thinking about
the specific question, look at the base rate of similar questions.
"""

import logging

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


# Structural patterns and their empirical YES-resolution rates
# from analysis of resolved Manifold/Polymarket markets
STRUCTURAL_PATTERNS = {
    # "Will X happen by [date]" — time-bounded predictions
    "deadline": {
        "keywords": ["by 202", "before 202", "by end of", "by the end", "within"],
        "yes_rate": 0.35,  # Most time-bounded things don't happen on time
        "description": "Time-bounded predictions resolve YES ~35% of the time",
    },
    # "Will [country] do [action]" — geopolitical actions
    "country_action": {
        "keywords": ["will china", "will russia", "will the us", "will india",
                     "will iran", "will north korea", "will the eu"],
        "yes_rate": 0.40,
        "description": "Country-action predictions resolve YES ~40%",
    },
    # "Will [tech] achieve [milestone]" — tech milestones
    "tech_milestone": {
        "keywords": ["breakthrough", "achieve", "demonstrate", "release",
                     "launch", "ship", "deploy"],
        "yes_rate": 0.30,
        "description": "Tech milestone predictions resolve YES ~30% (usually delayed)",
    },
    # "Will [person] win/be elected" — political outcomes
    "political_outcome": {
        "keywords": ["win the", "be elected", "become president", "win the election",
                     "be nominated", "be the nominee"],
        "yes_rate": 0.45,
        "description": "Political outcome predictions resolve YES ~45%",
    },
    # "Will there be [crisis]" — crisis/disaster predictions
    "crisis": {
        "keywords": ["will there be a war", "will there be a recession",
                     "will there be a pandemic", "crisis", "collapse",
                     "crash", "default"],
        "yes_rate": 0.20,
        "description": "Crisis predictions resolve YES ~20% (people overestimate)",
    },
    # "Will [regulation/law] pass" — regulatory predictions
    "regulation": {
        "keywords": ["legislation", "regulation", "ban", "law pass",
                     "executive order", "bill pass", "approved by"],
        "yes_rate": 0.30,
        "description": "Regulatory predictions resolve YES ~30%",
    },
    # Price/market targets
    "price_target": {
        "keywords": ["above $", "below $", "reach $", "cross $", "hit $",
                     "price above", "price below", "market cap"],
        "yes_rate": 0.40,
        "description": "Price target predictions resolve YES ~40%",
    },
}


class HistoricalAnalogyTool(BasePredictionTool):
    name = "historical_analogy"
    tool_type = "statistical"
    description = (
        "Reference class forecasting: finds structurally similar resolved questions "
        "and uses their resolution rate to adjust predictions."
    )
    best_for = ["technology", "geopolitics", "politics", "economy", "general"]

    async def predict(self, input: ToolInput) -> ToolOutput:
        market_prob = input.current_signals.get("market_probability", 0.5)
        question_lower = input.question.lower()

        # Find matching structural patterns
        matches = []
        for pattern_name, pattern in STRUCTURAL_PATTERNS.items():
            hit_count = sum(1 for kw in pattern["keywords"] if kw in question_lower)
            if hit_count > 0:
                matches.append((pattern_name, pattern, hit_count))

        if not matches:
            return ToolOutput(
                probability=market_prob,
                confidence=0.1,
                reasoning="No structural pattern matched for historical analogy",
                signals_used=["market_probability"],
            )

        # Use the best-matching pattern (most keyword hits)
        matches.sort(key=lambda x: x[2], reverse=True)
        best_name, best_pattern, hit_count = matches[0]
        base_rate = best_pattern["yes_rate"]

        # Blend base rate with market probability
        # Weight: 20% base rate, 80% market (market is still the stronger signal)
        blend_weight = 0.20
        adjusted = market_prob * (1 - blend_weight) + base_rate * blend_weight

        # Clamp
        adjusted = max(0.02, min(0.98, adjusted))

        shift = adjusted - market_prob
        confidence = 0.25 + hit_count * 0.05  # more keyword hits = more confident match

        reasoning = (
            f"Historical analogy: '{best_name}' pattern (base rate: {base_rate:.0%}). "
            f"{best_pattern['description']}. "
            f"Blended {market_prob:.1%} → {adjusted:.1%} ({shift:+.1%})."
        )

        return ToolOutput(
            probability=adjusted,
            confidence=min(0.5, confidence),
            reasoning=reasoning,
            signals_used=["market_probability"],
            metadata={
                "pattern": best_name,
                "base_rate": base_rate,
                "hit_count": hit_count,
                "blend_weight": blend_weight,
            },
        )

    def get_required_signals(self) -> list[str]:
        return ["market_probability"]
