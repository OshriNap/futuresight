"""Scientific Experiment Framework

Implements the scientific method for prediction tool evaluation:
1. Hypothesis: "Tool X performs better than Tool Y for category Z"
2. Experiment Design: Define conditions, metrics, sample size
3. Data Collection: Run both tools on same inputs
4. Statistical Analysis: Hypothesis testing, confidence intervals
5. Conclusion: Accept/reject hypothesis with evidence

This allows the system to make data-driven decisions about which tools to use.
"""

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    INCONCLUSIVE = "inconclusive"


@dataclass
class Hypothesis:
    """A testable hypothesis about prediction tool performance."""
    description: str  # e.g., "LLM reasoning outperforms market consensus for geopolitical events"
    tool_a: str  # control tool
    tool_b: str  # treatment tool
    category: str | None  # which category to test on (None = all)
    metric: str  # which loss function to compare (e.g., "brier_score")
    direction: str = "lower"  # "lower" = tool_b should have lower metric, "higher" = higher
    min_effect_size: float = 0.02  # minimum meaningful difference


@dataclass
class ExperimentResult:
    """Result of a single prediction in an experiment."""
    experiment_id: str
    prediction_input_hash: str  # hash of the input to ensure same inputs
    tool_a_name: str
    tool_a_prediction: float
    tool_b_name: str
    tool_b_prediction: float
    actual_outcome: float | None = None  # Set when resolved
    tool_a_loss: float | None = None
    tool_b_loss: float | None = None


@dataclass
class ExperimentAnalysis:
    """Statistical analysis of an experiment."""
    mean_a: float
    mean_b: float
    std_a: float
    std_b: float
    n: int
    effect_size: float  # Cohen's d
    t_statistic: float
    p_value: float
    confidence_interval_95: tuple[float, float]  # 95% CI for difference
    is_significant: bool
    conclusion: str
    recommendation: str


@dataclass
class Experiment:
    """A complete scientific experiment comparing two prediction tools."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    hypothesis: Hypothesis | None = None
    status: ExperimentStatus = ExperimentStatus.DRAFT
    required_sample_size: int = 30  # minimum for statistical significance
    results: list[ExperimentResult] = field(default_factory=list)
    analysis: ExperimentAnalysis | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    def add_result(self, result: ExperimentResult):
        self.results.append(result)

    def resolve_result(self, idx: int, actual: float, loss_fn):
        """Resolve a result with the actual outcome and compute losses."""
        result = self.results[idx]
        result.actual_outcome = actual
        result.tool_a_loss = loss_fn.compute(result.tool_a_prediction, actual).value
        result.tool_b_loss = loss_fn.compute(result.tool_b_prediction, actual).value

    def get_resolved_results(self) -> list[ExperimentResult]:
        return [r for r in self.results if r.actual_outcome is not None]

    def can_analyze(self) -> bool:
        resolved = self.get_resolved_results()
        return len(resolved) >= self.required_sample_size

    def analyze(self) -> ExperimentAnalysis:
        """Perform statistical analysis on resolved results."""
        resolved = self.get_resolved_results()
        n = len(resolved)

        if n < 2:
            return ExperimentAnalysis(
                mean_a=0, mean_b=0, std_a=0, std_b=0, n=n,
                effect_size=0, t_statistic=0, p_value=1.0,
                confidence_interval_95=(0, 0),
                is_significant=False,
                conclusion="Insufficient data for analysis",
                recommendation="Continue collecting data",
            )

        losses_a = [r.tool_a_loss for r in resolved]
        losses_b = [r.tool_b_loss for r in resolved]

        mean_a = sum(losses_a) / n
        mean_b = sum(losses_b) / n

        var_a = sum((x - mean_a) ** 2 for x in losses_a) / (n - 1) if n > 1 else 0
        var_b = sum((x - mean_b) ** 2 for x in losses_b) / (n - 1) if n > 1 else 0
        std_a = math.sqrt(var_a)
        std_b = math.sqrt(var_b)

        # Paired t-test (same inputs, different tools)
        differences = [b - a for a, b in zip(losses_a, losses_b)]
        mean_diff = sum(differences) / n
        var_diff = sum((d - mean_diff) ** 2 for d in differences) / (n - 1) if n > 1 else 0
        std_diff = math.sqrt(var_diff)
        se_diff = std_diff / math.sqrt(n) if n > 0 else 1

        t_stat = mean_diff / se_diff if se_diff > 0 else 0

        # Approximate p-value using normal distribution (valid for n >= 30)
        p_value = 2 * (1 - _normal_cdf(abs(t_stat)))

        # 95% confidence interval
        z_95 = 1.96
        ci_low = mean_diff - z_95 * se_diff
        ci_high = mean_diff + z_95 * se_diff

        # Effect size (Cohen's d)
        pooled_std = math.sqrt((var_a + var_b) / 2) if (var_a + var_b) > 0 else 1
        effect_size = abs(mean_a - mean_b) / pooled_std

        is_significant = p_value < 0.05

        # Generate conclusion
        tool_a = self.hypothesis.tool_a
        tool_b = self.hypothesis.tool_b

        if not is_significant:
            conclusion = (f"No statistically significant difference between {tool_a} and {tool_b} "
                         f"(p={p_value:.4f}, n={n})")
            recommendation = "Continue collecting data or accept tools are equivalent"
        elif mean_b < mean_a:  # lower loss = better
            conclusion = (f"{tool_b} significantly outperforms {tool_a} "
                         f"(mean loss: {mean_b:.4f} vs {mean_a:.4f}, p={p_value:.4f}, d={effect_size:.2f})")
            recommendation = f"Increase weight of {tool_b} for {self.hypothesis.category or 'all'} predictions"
        else:
            conclusion = (f"{tool_a} significantly outperforms {tool_b} "
                         f"(mean loss: {mean_a:.4f} vs {mean_b:.4f}, p={p_value:.4f}, d={effect_size:.2f})")
            recommendation = f"Keep {tool_a} as primary for {self.hypothesis.category or 'all'} predictions"

        # Classify effect size
        if effect_size < 0.2:
            effect_label = "negligible"
        elif effect_size < 0.5:
            effect_label = "small"
        elif effect_size < 0.8:
            effect_label = "medium"
        else:
            effect_label = "large"

        conclusion += f" Effect size: {effect_label} ({effect_size:.2f})"

        self.analysis = ExperimentAnalysis(
            mean_a=mean_a, mean_b=mean_b, std_a=std_a, std_b=std_b, n=n,
            effect_size=effect_size, t_statistic=t_stat, p_value=p_value,
            confidence_interval_95=(ci_low, ci_high),
            is_significant=is_significant,
            conclusion=conclusion,
            recommendation=recommendation,
        )
        self.status = ExperimentStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        return self.analysis


def _normal_cdf(x: float) -> float:
    """Approximate cumulative distribution function for standard normal."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
