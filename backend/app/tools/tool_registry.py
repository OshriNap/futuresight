"""Tool Registry - manages all available prediction tools.

The registry is used by the Forecaster agent to select which tools to use
for each prediction. Over time, the system learns which tools work best
for which categories by tracking performance.
"""

import logging
from dataclasses import dataclass

from app.tools.base_rate_tool import BaseRateTool
from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput
from app.tools.contrarian import ContrarianTool
from app.tools.extrapolation import AdvancedExtrapolatorTool
from app.tools.graph_context import GraphContextTool
from app.tools.llm_reasoner import LLMReasonerTool
from app.tools.market_consensus import MarketConsensusTool
from app.tools.multi_market_ensemble import MultiMarketEnsembleTool
from app.tools.nli_tool import NLITool
from app.tools.trend_extrapolator import TrendExtrapolatorTool

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    tool_name: str
    output: ToolOutput
    weight: float  # How much to weight this tool's prediction in the ensemble


class ToolRegistry:
    """Central registry of all prediction tools.

    Manages tool selection, execution, and performance tracking.
    """

    def __init__(self):
        self._tools: dict[str, BasePredictionTool] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register all built-in tools."""
        for tool_class in [
            MarketConsensusTool,
            MultiMarketEnsembleTool,
            TrendExtrapolatorTool,
            AdvancedExtrapolatorTool,
            LLMReasonerTool,
            BaseRateTool,
            NLITool,
            GraphContextTool,
            ContrarianTool,
        ]:
            tool = tool_class()
            self._tools[tool.name] = tool

    def register(self, tool: BasePredictionTool):
        """Register a custom prediction tool."""
        self._tools[tool.name] = tool
        logger.info(f"Registered prediction tool: {tool.name} ({tool.tool_type})")

    def get_tool(self, name: str) -> BasePredictionTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[BasePredictionTool]:
        return list(self._tools.values())

    def select_tools(self, input: ToolInput, performance_data: dict | None = None) -> list[str]:
        """Select the best tools for a given input based on category, signals, and past performance.

        Args:
            input: The prediction input
            performance_data: Dict of {tool_name: {"brier_score": float, "count": int}} per category

        Returns:
            List of tool names to use, ordered by expected quality.
        """
        candidates = []
        for name, tool in self._tools.items():
            can_handle, reason = tool.can_handle(input)
            if not can_handle:
                continue

            # Score based on: is this a best-for category? + historical performance
            score = 0.5  # baseline

            if input.category in tool.best_for:
                score += 0.2

            if performance_data and name in performance_data:
                perf = performance_data[name]
                if perf["count"] >= 5:
                    # Lower Brier = better, so invert
                    score += (1 - perf["brier_score"]) * 0.3

            candidates.append((name, score))

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Return top tools (at least 2, up to 4)
        selected = [name for name, _ in candidates[:4]]
        if not selected:
            selected = ["market_consensus"]  # fallback

        return selected

    async def run_tools(
        self, input: ToolInput, tool_names: list[str], performance_data: dict | None = None
    ) -> list[ToolResult]:
        """Run selected tools and return weighted results."""
        results = []
        for name in tool_names:
            tool = self._tools.get(name)
            if not tool:
                continue
            try:
                output = await tool.predict(input)

                # Calculate weight based on confidence and historical performance
                weight = output.confidence
                if performance_data and name in performance_data:
                    perf = performance_data[name]
                    if perf["count"] >= 5:
                        weight *= (1 - perf["brier_score"])

                results.append(ToolResult(tool_name=name, output=output, weight=weight))
            except Exception as e:
                logger.error(f"Tool {name} failed: {e}")

        return results

    def ensemble_prediction(self, results: list[ToolResult]) -> ToolOutput:
        """Combine multiple tool outputs using log-linear pooling with extremization.

        Log-linear pooling is superior to linear averaging for probability
        forecasts — it properly handles the [0,1] bounded nature of probabilities.
        Extremization pushes the result away from 0.5 to correct for typical
        regression-to-the-mean bias in averaged forecasts.
        """
        import math

        if not results:
            return ToolOutput(probability=0.5, confidence=0.1, reasoning="No tools produced results", signals_used=[])

        if len(results) == 1:
            r = results[0]
            r.output.metadata["data_signals"] = self._build_data_signals(results, r.output.probability)
            return r.output

        total_weight = sum(r.weight for r in results)
        if total_weight == 0:
            total_weight = len(results)
            for r in results:
                r.weight = 1.0

        # Log-linear pooling: geometric mean in log-odds space
        # This properly handles probabilities near 0 and 1
        log_odds_sum = 0.0
        for r in results:
            p = max(0.01, min(0.99, r.output.probability))  # clamp to avoid log(0)
            norm_weight = r.weight / total_weight
            log_odds_sum += norm_weight * math.log(p / (1 - p))

        # Convert back from log-odds to probability
        weighted_prob = 1.0 / (1.0 + math.exp(-log_odds_sum))

        # Extremize: push away from 0.5 by factor d > 1
        # d=1.2 is a standard correction from forecasting literature
        EXTREMIZE_FACTOR = 1.2
        log_odds = math.log(weighted_prob / (1 - weighted_prob))
        extremized_odds = log_odds * EXTREMIZE_FACTOR
        weighted_prob = 1.0 / (1.0 + math.exp(-extremized_odds))

        # Clamp to [0.02, 0.98]
        weighted_prob = max(0.02, min(0.98, weighted_prob))

        max_confidence = max(r.output.confidence for r in results)

        # Build reasoning
        parts = [f"{r.tool_name}: {r.output.probability:.1%} (w={r.weight:.2f})" for r in results]
        reasoning = f"Ensemble of {len(results)} tools: {', '.join(parts)}. Weighted result: {weighted_prob:.1%}"

        all_signals = set()
        for r in results:
            all_signals.update(r.output.signals_used)

        data_signals = self._build_data_signals(results, weighted_prob)

        return ToolOutput(
            probability=weighted_prob,
            confidence=max_confidence * 0.9,  # Ensemble is slightly more confident
            reasoning=reasoning,
            signals_used=list(all_signals),
            metadata={
                "ensemble_size": len(results),
                "tool_names": [r.tool_name for r in results],
                "data_signals": data_signals,
            },
        )

    @staticmethod
    def _build_data_signals(results: list["ToolResult"], ensemble_prob: float) -> dict:
        """Build structured data_signals from tool results for frontend display."""
        factors = []
        for r in results:
            norm_weight = r.weight / max(sum(rr.weight for rr in results), 1e-9)
            if r.output.probability >= ensemble_prob:
                direction = "supports"
            elif abs(r.output.probability - ensemble_prob) < 0.05:
                direction = "neutral"
            else:
                direction = "contradicts"

            counterfactual = None
            without = ensemble_prob - (r.output.probability * norm_weight)
            remaining = 1 - norm_weight
            if remaining > 0:
                alt_prob = without / remaining
                alt_prob = max(0.0, min(1.0, alt_prob))
                counterfactual = f"Without this signal, probability would shift to ~{alt_prob:.0%}"

            factors.append({
                "signal": r.output.reasoning[:120] if r.output.reasoning else r.tool_name,
                "direction": direction,
                "weight": round(norm_weight, 3),
                "counterfactual": counterfactual,
            })

        return {
            "factors": factors,
            "sources": [],  # Populated by collectors when source data is available
            "method": "ensemble",
            "tools_used": [r.tool_name for r in results],
        }


# Global registry instance
registry = ToolRegistry()
