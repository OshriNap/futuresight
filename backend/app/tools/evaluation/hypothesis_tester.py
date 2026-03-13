"""Hypothesis Testing Framework

Provides statistical tools for testing hypotheses about the prediction system.

Supports multiple types of tests:
1. A/B tests between tools (paired t-test)
2. Calibration tests (chi-squared goodness of fit)
3. Trend detection (is a tool improving over time?)
4. Regime detection (has the environment changed, making old data less relevant?)
"""

import math
from dataclasses import dataclass
from enum import Enum


class TestType(str, Enum):
    PAIRED_T = "paired_t_test"
    WELCH_T = "welch_t_test"  # For unequal variances
    SIGN_TEST = "sign_test"  # Non-parametric alternative
    CALIBRATION_CHI2 = "calibration_chi_squared"
    TREND_MANN_KENDALL = "trend_mann_kendall"


@dataclass
class TestResult:
    test_type: TestType
    test_statistic: float
    p_value: float
    degrees_of_freedom: float | None
    is_significant_05: bool  # p < 0.05
    is_significant_01: bool  # p < 0.01
    effect_size: float | None
    interpretation: str
    details: dict


class HypothesisTester:
    """Statistical hypothesis testing for prediction evaluation."""

    def paired_t_test(self, losses_a: list[float], losses_b: list[float]) -> TestResult:
        """Paired t-test: are the two tools different on the same inputs?

        H0: mean(losses_a) = mean(losses_b)
        H1: mean(losses_a) != mean(losses_b)
        """
        n = len(losses_a)
        assert n == len(losses_b), "Paired test requires equal-length arrays"
        assert n >= 2, "Need at least 2 observations"

        diffs = [a - b for a, b in zip(losses_a, losses_b)]
        mean_diff = sum(diffs) / n
        var_diff = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1)
        se = math.sqrt(var_diff / n) if var_diff > 0 else 1e-10

        t_stat = mean_diff / se
        df = n - 1

        # Approximate p-value
        p_value = 2 * (1 - _t_cdf(abs(t_stat), df))

        # Effect size (Cohen's d for paired)
        sd_diff = math.sqrt(var_diff)
        effect_size = abs(mean_diff) / sd_diff if sd_diff > 0 else 0

        better = "A (lower loss)" if mean_diff > 0 else "B (lower loss)"
        interp = (f"Mean difference: {mean_diff:.4f} (SE={se:.4f}). "
                  f"{'Significant' if p_value < 0.05 else 'Not significant'} at p<0.05. "
                  f"Tool {better} by {abs(mean_diff):.4f} on average.")

        return TestResult(
            test_type=TestType.PAIRED_T,
            test_statistic=t_stat,
            p_value=p_value,
            degrees_of_freedom=df,
            is_significant_05=p_value < 0.05,
            is_significant_01=p_value < 0.01,
            effect_size=effect_size,
            interpretation=interp,
            details={"mean_diff": mean_diff, "se": se, "n": n},
        )

    def sign_test(self, losses_a: list[float], losses_b: list[float]) -> TestResult:
        """Non-parametric sign test: does one tool win more often?

        More robust than t-test for non-normal distributions.
        H0: P(A wins) = P(B wins) = 0.5
        """
        n = len(losses_a)
        wins_b = sum(1 for a, b in zip(losses_a, losses_b) if b < a)  # B has lower loss
        wins_a = sum(1 for a, b in zip(losses_a, losses_b) if a < b)
        ties = n - wins_a - wins_b
        effective_n = wins_a + wins_b  # Exclude ties

        if effective_n == 0:
            return TestResult(
                test_type=TestType.SIGN_TEST, test_statistic=0, p_value=1.0,
                degrees_of_freedom=None, is_significant_05=False, is_significant_01=False,
                effect_size=None, interpretation="All predictions tied - no difference detected",
                details={"wins_a": 0, "wins_b": 0, "ties": n},
            )

        # Normal approximation to binomial
        k = min(wins_a, wins_b)
        z = (k - effective_n / 2) / math.sqrt(effective_n / 4) if effective_n > 0 else 0
        p_value = 2 * _normal_cdf(z)  # Two-sided

        winner = "A" if wins_a > wins_b else "B"
        interp = (f"Tool {winner} wins {max(wins_a, wins_b)}/{effective_n} comparisons "
                  f"(ties: {ties}). p={p_value:.4f}")

        return TestResult(
            test_type=TestType.SIGN_TEST,
            test_statistic=z,
            p_value=p_value,
            degrees_of_freedom=None,
            is_significant_05=p_value < 0.05,
            is_significant_01=p_value < 0.01,
            effect_size=max(wins_a, wins_b) / effective_n if effective_n > 0 else None,
            interpretation=interp,
            details={"wins_a": wins_a, "wins_b": wins_b, "ties": ties, "effective_n": effective_n},
        )

    def calibration_test(self, predictions: list[tuple[float, float]], n_bins: int = 10) -> TestResult:
        """Chi-squared test for calibration.

        H0: predictions are well-calibrated (predicted probs match observed frequencies)
        H1: predictions are miscalibrated
        """
        bins = [{"preds": [], "actuals": []} for _ in range(n_bins)]
        for pred, actual in predictions:
            idx = min(int(pred * n_bins), n_bins - 1)
            bins[idx]["preds"].append(pred)
            bins[idx]["actuals"].append(actual)

        chi2 = 0.0
        df = 0
        bin_details = []

        for i, b in enumerate(bins):
            if not b["preds"]:
                continue
            n_bin = len(b["preds"])
            expected_rate = sum(b["preds"]) / n_bin  # What we predicted
            observed_rate = sum(b["actuals"]) / n_bin  # What actually happened

            expected_count = expected_rate * n_bin
            observed_count = sum(b["actuals"])

            if expected_count > 0 and n_bin >= 5:  # Chi-squared requires expected >= 5
                contribution = (observed_count - expected_count) ** 2 / expected_count
                chi2 += contribution
                df += 1
                bin_details.append({
                    "bin": f"{i/n_bins:.1f}-{(i+1)/n_bins:.1f}",
                    "n": n_bin,
                    "predicted_avg": expected_rate,
                    "observed_rate": observed_rate,
                    "chi2_contribution": contribution,
                })

        df = max(1, df - 1)  # Subtract 1 for constraint
        p_value = 1 - _chi2_cdf(chi2, df)

        ece = sum(abs(b["predicted_avg"] - b["observed_rate"]) * b["n"]
                  for b in bin_details) / len(predictions) if bin_details else 0

        interp = (f"Chi-squared={chi2:.2f} (df={df}), p={p_value:.4f}. "
                  f"ECE={ece:.4f}. "
                  f"{'Miscalibrated' if p_value < 0.05 else 'Well-calibrated'} at p<0.05.")

        return TestResult(
            test_type=TestType.CALIBRATION_CHI2,
            test_statistic=chi2,
            p_value=p_value,
            degrees_of_freedom=df,
            is_significant_05=p_value < 0.05,
            is_significant_01=p_value < 0.01,
            effect_size=ece,
            interpretation=interp,
            details={"bins": bin_details, "ece": ece},
        )

    def trend_test(self, values: list[float]) -> TestResult:
        """Mann-Kendall trend test: is the tool improving or degrading over time?

        Tests for monotonic trend in a time series of scores.
        H0: No trend
        H1: Monotonic trend exists
        """
        n = len(values)
        if n < 4:
            return TestResult(
                test_type=TestType.TREND_MANN_KENDALL, test_statistic=0, p_value=1.0,
                degrees_of_freedom=None, is_significant_05=False, is_significant_01=False,
                effect_size=None, interpretation="Need at least 4 data points for trend test",
                details={},
            )

        # Calculate S statistic
        s = 0
        for i in range(n - 1):
            for j in range(i + 1, n):
                diff = values[j] - values[i]
                if diff > 0:
                    s += 1
                elif diff < 0:
                    s -= 1

        # Variance of S
        var_s = n * (n - 1) * (2 * n + 5) / 18

        # Z-statistic
        if s > 0:
            z = (s - 1) / math.sqrt(var_s)
        elif s < 0:
            z = (s + 1) / math.sqrt(var_s)
        else:
            z = 0

        p_value = 2 * (1 - _normal_cdf(abs(z)))

        # Kendall's tau as effect size
        tau = s / (n * (n - 1) / 2)

        trend_dir = "improving (decreasing loss)" if s < 0 else "degrading (increasing loss)" if s > 0 else "stable"
        interp = (f"Trend: {trend_dir}. Kendall's tau={tau:.3f}, Z={z:.2f}, p={p_value:.4f}. "
                  f"{'Significant trend' if p_value < 0.05 else 'No significant trend'} detected.")

        return TestResult(
            test_type=TestType.TREND_MANN_KENDALL,
            test_statistic=z,
            p_value=p_value,
            degrees_of_freedom=None,
            is_significant_05=p_value < 0.05,
            is_significant_01=p_value < 0.01,
            effect_size=tau,
            interpretation=interp,
            details={"s_statistic": s, "tau": tau, "n": n, "trend_direction": trend_dir},
        )


def _normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _t_cdf(t: float, df: float) -> float:
    """Approximate t-distribution CDF using normal approximation for large df."""
    if df >= 30:
        return _normal_cdf(t)
    # Rough approximation for smaller df
    x = df / (df + t * t)
    return 1 - 0.5 * _incomplete_beta(df / 2, 0.5, x)


def _incomplete_beta(a: float, b: float, x: float) -> float:
    """Very rough approximation of incomplete beta function."""
    # Use normal approximation
    mu = a / (a + b)
    var = a * b / ((a + b) ** 2 * (a + b + 1))
    return _normal_cdf((x - mu) / math.sqrt(var)) if var > 0 else float(x >= mu)


def _chi2_cdf(x: float, df: int) -> float:
    """Approximate chi-squared CDF using Wilson-Hilferty transformation."""
    if df <= 0 or x <= 0:
        return 0.0
    z = ((x / df) ** (1/3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
    return _normal_cdf(z)
