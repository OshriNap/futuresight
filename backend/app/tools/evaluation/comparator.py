"""Tool Comparator

Systematic comparison of prediction tools across dimensions:
- Overall accuracy (Brier, Log Loss, Spherical)
- Category-specific performance
- Calibration quality
- Sensitivity analysis (how small input changes affect predictions)
- Speed and reliability
- Failure modes (when and how each tool fails)
"""

import logging
from dataclasses import dataclass

from app.tools.base_tool import BasePredictionTool, ToolInput, ToolOutput
from app.tools.loss_functions.registry import LOSS_FUNCTIONS, BaseLossFunction, CalibrationLoss

logger = logging.getLogger(__name__)


@dataclass
class ToolProfile:
    """Comprehensive profile of a prediction tool's characteristics."""
    tool_name: str
    tool_type: str

    # Performance across loss functions
    scores: dict[str, float]  # {loss_name: avg_score}

    # Category breakdown
    category_scores: dict[str, dict[str, float]]  # {category: {loss_name: score}}

    # Calibration
    calibration_curve: dict | None
    expected_calibration_error: float | None

    # Behavioral characteristics
    avg_confidence: float
    confidence_range: tuple[float, float]
    prediction_range: tuple[float, float]  # how spread out are predictions
    extremity_rate: float  # % of predictions > 0.9 or < 0.1

    # Reliability
    failure_rate: float  # % of times tool couldn't produce output
    avg_signals_used: float  # how many signals it typically uses

    # Comparative
    beats_baseline: bool  # Does it beat simple market consensus?
    best_categories: list[str]
    worst_categories: list[str]


@dataclass
class ComparisonReport:
    """Head-to-head comparison of two tools."""
    tool_a: str
    tool_b: str
    category: str | None  # None = overall

    # Win rates
    tool_a_wins: int
    tool_b_wins: int
    ties: int
    total: int

    # Per loss function
    loss_comparison: dict[str, dict]  # {loss_name: {tool_a: score, tool_b: score, winner: name}}

    # Statistical significance
    is_significant: bool
    p_value: float | None

    # Insights
    insights: list[str]
    recommendation: str


class ToolComparator:
    """Compares prediction tools scientifically."""

    def __init__(self):
        self.loss_functions = LOSS_FUNCTIONS
        self.calibration = CalibrationLoss()

    def profile_tool(
        self,
        tool: BasePredictionTool,
        results: list[dict],  # [{input: ToolInput, output: ToolOutput, actual: float}]
    ) -> ToolProfile:
        """Build a comprehensive profile of a tool's performance."""
        if not results:
            return ToolProfile(
                tool_name=tool.name, tool_type=tool.tool_type,
                scores={}, category_scores={}, calibration_curve=None,
                expected_calibration_error=None, avg_confidence=0,
                confidence_range=(0, 0), prediction_range=(0, 0),
                extremity_rate=0, failure_rate=0, avg_signals_used=0,
                beats_baseline=False, best_categories=[], worst_categories=[],
            )

        # Compute all loss functions
        predictions = [(r["output"].probability, r["actual"]) for r in results]
        scores = {}
        for name, loss_fn in self.loss_functions.items():
            batch_result = loss_fn.compute_batch(predictions)
            scores[name] = batch_result.value

        # Category breakdown
        by_category: dict[str, list] = {}
        for r in results:
            cat = r["input"].category
            by_category.setdefault(cat, []).append((r["output"].probability, r["actual"]))

        category_scores = {}
        for cat, cat_preds in by_category.items():
            category_scores[cat] = {}
            for name, loss_fn in self.loss_functions.items():
                category_scores[cat][name] = loss_fn.compute_batch(cat_preds).value

        # Calibration
        cal_data = self.calibration.compute_calibration_curve(predictions)

        # Behavioral stats
        confidences = [r["output"].confidence for r in results]
        probs = [r["output"].probability for r in results]
        signals_counts = [len(r["output"].signals_used) for r in results]

        extreme_count = sum(1 for p in probs if p > 0.9 or p < 0.1)

        # Best/worst categories by Brier
        if category_scores:
            sorted_cats = sorted(category_scores.items(), key=lambda x: x[1].get("brier_score", 999))
            best = [c[0] for c in sorted_cats[:3]]
            worst = [c[0] for c in sorted_cats[-3:]]
        else:
            best, worst = [], []

        return ToolProfile(
            tool_name=tool.name,
            tool_type=tool.tool_type,
            scores=scores,
            category_scores=category_scores,
            calibration_curve=cal_data,
            expected_calibration_error=cal_data["expected_calibration_error"],
            avg_confidence=sum(confidences) / len(confidences),
            confidence_range=(min(confidences), max(confidences)),
            prediction_range=(min(probs), max(probs)),
            extremity_rate=extreme_count / len(probs),
            failure_rate=0,  # Would track externally
            avg_signals_used=sum(signals_counts) / len(signals_counts),
            beats_baseline=scores.get("brier_score", 1) < 0.25,  # Naive baseline ~0.25
            best_categories=best,
            worst_categories=worst,
        )

    def compare_tools(
        self,
        tool_a_results: list[dict],
        tool_b_results: list[dict],
        tool_a_name: str,
        tool_b_name: str,
        category: str | None = None,
    ) -> ComparisonReport:
        """Head-to-head comparison of two tools on the same inputs."""
        # Match results by input (assuming they're aligned)
        n = min(len(tool_a_results), len(tool_b_results))
        if n == 0:
            return ComparisonReport(
                tool_a=tool_a_name, tool_b=tool_b_name, category=category,
                tool_a_wins=0, tool_b_wins=0, ties=0, total=0,
                loss_comparison={}, is_significant=False, p_value=None,
                insights=["No data to compare"], recommendation="Collect more data",
            )

        wins_a, wins_b, ties = 0, 0, 0
        loss_comparison = {}
        insights = []

        for loss_name, loss_fn in self.loss_functions.items():
            a_losses = [loss_fn.compute(r["output"].probability, r["actual"]).value for r in tool_a_results[:n]]
            b_losses = [loss_fn.compute(r["output"].probability, r["actual"]).value for r in tool_b_results[:n]]

            avg_a = sum(a_losses) / n
            avg_b = sum(b_losses) / n

            lower_is_better = loss_fn.lower_is_better
            if lower_is_better:
                winner = tool_a_name if avg_a < avg_b else tool_b_name
            else:
                winner = tool_a_name if avg_a > avg_b else tool_b_name

            loss_comparison[loss_name] = {
                "tool_a_avg": avg_a,
                "tool_b_avg": avg_b,
                "winner": winner,
                "difference": abs(avg_a - avg_b),
                "pct_difference": abs(avg_a - avg_b) / max(avg_a, avg_b, 0.001) * 100,
            }

        # Per-prediction wins (using Brier as primary)
        brier = self.loss_functions["brier_score"]
        for i in range(n):
            loss_a = brier.compute(tool_a_results[i]["output"].probability, tool_a_results[i]["actual"]).value
            loss_b = brier.compute(tool_b_results[i]["output"].probability, tool_b_results[i]["actual"]).value
            if abs(loss_a - loss_b) < 0.001:
                ties += 1
            elif loss_a < loss_b:
                wins_a += 1
            else:
                wins_b += 1

        # Generate insights
        for loss_name, comp in loss_comparison.items():
            pct = comp["pct_difference"]
            if pct > 10:
                insights.append(
                    f"{comp['winner']} is {pct:.1f}% better on {loss_name} "
                    f"({comp['tool_a_avg']:.4f} vs {comp['tool_b_avg']:.4f})"
                )

        # Recommendation
        brier_comp = loss_comparison.get("brier_score", {})
        winner = brier_comp.get("winner", "neither")
        pct_diff = brier_comp.get("pct_difference", 0)

        if pct_diff < 5:
            recommendation = f"{tool_a_name} and {tool_b_name} perform similarly. Consider using both in ensemble."
        elif pct_diff < 15:
            recommendation = f"Slight advantage to {winner}. Use {winner} as primary, keep other in ensemble."
        else:
            recommendation = f"Clear advantage to {winner}. Prioritize {winner} for {category or 'this type of'} predictions."

        return ComparisonReport(
            tool_a=tool_a_name, tool_b=tool_b_name, category=category,
            tool_a_wins=wins_a, tool_b_wins=wins_b, ties=ties, total=n,
            loss_comparison=loss_comparison,
            is_significant=n >= 30 and pct_diff > 5,
            p_value=None,  # Would compute from experiment framework
            insights=insights,
            recommendation=recommendation,
        )

    def sensitivity_analysis(
        self,
        tool: BasePredictionTool,
        base_input: ToolInput,
        signal_name: str,
        values: list[float],
    ) -> list[dict]:
        """Test how sensitive a tool is to changes in a specific signal.

        Varies one signal while keeping everything else constant.
        Useful for understanding what drives each tool's predictions.
        """
        # This would need to be run async, but showing the structure
        results = []
        for val in values:
            modified_input = ToolInput(
                question=base_input.question,
                category=base_input.category,
                current_signals={**base_input.current_signals, signal_name: val},
                historical_data=base_input.historical_data,
                time_horizon=base_input.time_horizon,
            )
            results.append({
                "signal_value": val,
                "input": modified_input,
                # output would be filled by async predict call
            })
        return results
