"""Loss Function Registry

Different loss functions measure different aspects of prediction quality.
The system can switch between them or combine them to optimize for different goals.

Key insight: the choice of loss function CHANGES what "good" means.
- Brier score: rewards calibration + accuracy equally
- Log loss: heavily penalizes confident wrong predictions
- Spherical: rewards sharpness (being decisive)

Meta-agents evaluate which loss function best matches the system's goals
and can recommend switching based on observed behavior.
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LossResult:
    """Result of computing a loss function."""
    value: float  # The loss value
    name: str  # Name of the loss function
    interpretation: str  # Human-readable interpretation
    properties: dict  # Additional properties (gradient, sensitivity, etc.)


class BaseLossFunction(ABC):
    """Abstract loss function for evaluating predictions."""

    name: str
    description: str
    lower_is_better: bool = True
    range: tuple[float, float] = (0.0, 1.0)  # Typical value range

    @abstractmethod
    def compute(self, predicted: float, actual: float) -> LossResult:
        """Compute loss for a single prediction.

        Args:
            predicted: Predicted probability [0, 1]
            actual: Actual outcome (0 or 1)
        """
        ...

    def compute_batch(self, predictions: list[tuple[float, float]]) -> LossResult:
        """Compute average loss over a batch of (predicted, actual) pairs."""
        if not predictions:
            return LossResult(value=0.0, name=self.name, interpretation="No data", properties={})
        results = [self.compute(p, a) for p, a in predictions]
        avg = sum(r.value for r in results) / len(results)
        return LossResult(
            value=avg,
            name=self.name,
            interpretation=f"Average {self.name} over {len(predictions)} predictions: {avg:.4f}",
            properties={"count": len(predictions), "min": min(r.value for r in results), "max": max(r.value for r in results)},
        )

    @abstractmethod
    def gradient(self, predicted: float, actual: float) -> float:
        """Compute gradient of loss w.r.t. predicted probability.
        Used for understanding sensitivity and for optimization.
        """
        ...


class BrierScore(BaseLossFunction):
    """Brier Score: (predicted - actual)²

    Properties:
    - Strictly proper: incentivizes honest probability estimates
    - Decomposes into: reliability + resolution - uncertainty
    - Symmetric around 0.5
    - Gentle gradient: doesn't overly punish confident mistakes
    """
    name = "brier_score"
    description = "Mean squared error of probability estimates. Balances calibration and accuracy."

    def compute(self, predicted: float, actual: float) -> LossResult:
        loss = (predicted - actual) ** 2
        return LossResult(
            value=loss,
            name=self.name,
            interpretation=f"Brier={loss:.4f} (pred={predicted:.2f}, actual={actual})",
            properties={"decomposition": "reliability + resolution - uncertainty"},
        )

    def gradient(self, predicted: float, actual: float) -> float:
        return 2 * (predicted - actual)


class LogLoss(BaseLossFunction):
    """Logarithmic Loss (Cross-Entropy): -[actual*log(pred) + (1-actual)*log(1-pred)]

    Properties:
    - Strictly proper scoring rule
    - HEAVILY punishes confident wrong predictions (approaching infinity)
    - Good for detecting overconfidence
    - Common in ML classification
    """
    name = "log_loss"
    description = "Cross-entropy loss. Severely punishes confident mistakes."
    range = (0.0, float("inf"))

    def compute(self, predicted: float, actual: float) -> LossResult:
        # Clamp to avoid log(0)
        p = max(1e-15, min(1 - 1e-15, predicted))
        loss = -(actual * math.log(p) + (1 - actual) * math.log(1 - p))
        return LossResult(
            value=loss,
            name=self.name,
            interpretation=f"LogLoss={loss:.4f} (pred={predicted:.2f}, actual={actual})"
                           + (" WARNING: high loss from confident wrong prediction!" if loss > 2 else ""),
            properties={"penalty_severity": "exponential for confident mistakes"},
        )

    def gradient(self, predicted: float, actual: float) -> float:
        p = max(1e-15, min(1 - 1e-15, predicted))
        return -actual / p + (1 - actual) / (1 - p)


class SphericalScore(BaseLossFunction):
    """Spherical Scoring Rule: predicted / sqrt(predicted² + (1-predicted)²)

    Properties:
    - Strictly proper
    - Rewards sharpness (being decisive, not wishy-washy)
    - Less sensitive to calibration than Brier
    - Good when you want the system to commit to predictions
    """
    name = "spherical_score"
    description = "Rewards sharp, decisive predictions. Higher is better."
    lower_is_better = False
    range = (0.0, 1.0)

    def compute(self, predicted: float, actual: float) -> LossResult:
        p = max(1e-15, min(1 - 1e-15, predicted))
        norm = math.sqrt(p ** 2 + (1 - p) ** 2)
        if actual == 1:
            score = p / norm
        else:
            score = (1 - p) / norm
        return LossResult(
            value=score,
            name=self.name,
            interpretation=f"Spherical={score:.4f} (higher=better, pred={predicted:.2f}, actual={actual})",
            properties={"measures": "sharpness + accuracy"},
        )

    def gradient(self, predicted: float, actual: float) -> float:
        p = max(1e-15, min(1 - 1e-15, predicted))
        norm = math.sqrt(p ** 2 + (1 - p) ** 2)
        if actual == 1:
            return (1 - p) ** 2 / norm ** 3
        else:
            return -(p ** 2) / norm ** 3


class CalibrationLoss(BaseLossFunction):
    """Calibration-focused loss.

    Measures how well probability buckets match observed frequencies.
    Not useful for single predictions - needs batch computation.

    Properties:
    - Specifically targets calibration (are 70% predictions right 70% of the time?)
    - Best used as a diagnostic, not as primary optimization target
    - Helps detect systematic overconfidence or underconfidence
    """
    name = "calibration_loss"
    description = "Measures deviation between predicted probabilities and observed frequencies."

    def compute(self, predicted: float, actual: float) -> LossResult:
        # Single-prediction calibration doesn't make much sense
        loss = abs(predicted - actual)
        return LossResult(
            value=loss,
            name=self.name,
            interpretation=f"Single-point calibration error: {loss:.4f}",
            properties={"note": "Use compute_calibration_curve for meaningful calibration analysis"},
        )

    def gradient(self, predicted: float, actual: float) -> float:
        return 1.0 if predicted > actual else -1.0

    def compute_calibration_curve(
        self, predictions: list[tuple[float, float]], n_bins: int = 10
    ) -> dict:
        """Compute calibration curve: bin predictions by confidence and compare to actual rates.

        Returns:
            Dict with bins, each containing:
            - bin_center: center of probability bin
            - predicted_avg: average predicted probability in bin
            - actual_rate: actual outcome rate in bin
            - count: number of predictions in bin
            - calibration_error: |predicted_avg - actual_rate|
        """
        bins = [{"predictions": [], "actuals": []} for _ in range(n_bins)]

        for pred, actual in predictions:
            bin_idx = min(int(pred * n_bins), n_bins - 1)
            bins[bin_idx]["predictions"].append(pred)
            bins[bin_idx]["actuals"].append(actual)

        curve = []
        total_ece = 0.0
        total_count = len(predictions)

        for i, bin_data in enumerate(bins):
            if not bin_data["predictions"]:
                continue
            count = len(bin_data["predictions"])
            pred_avg = sum(bin_data["predictions"]) / count
            actual_rate = sum(bin_data["actuals"]) / count
            cal_error = abs(pred_avg - actual_rate)
            total_ece += cal_error * count

            curve.append({
                "bin_center": (i + 0.5) / n_bins,
                "predicted_avg": pred_avg,
                "actual_rate": actual_rate,
                "count": count,
                "calibration_error": cal_error,
            })

        ece = total_ece / total_count if total_count > 0 else 0

        return {
            "curve": curve,
            "expected_calibration_error": ece,
            "n_bins": n_bins,
            "total_predictions": total_count,
        }


class WeightedLoss(BaseLossFunction):
    """Composite loss: weighted combination of multiple loss functions.

    Allows the system to optimize for multiple objectives simultaneously.
    Meta-agents can adjust weights based on what the system needs to improve.
    """
    name = "weighted_composite"
    description = "Weighted combination of multiple loss functions."

    def __init__(self, weights: dict[str, float] | None = None):
        self.components: dict[str, BaseLossFunction] = {
            "brier": BrierScore(),
            "log_loss": LogLoss(),
            "calibration": CalibrationLoss(),
        }
        self.weights = weights or {"brier": 0.5, "log_loss": 0.3, "calibration": 0.2}

    def compute(self, predicted: float, actual: float) -> LossResult:
        total = 0.0
        component_values = {}
        for name, loss_fn in self.components.items():
            weight = self.weights.get(name, 0)
            if weight <= 0:
                continue
            result = loss_fn.compute(predicted, actual)
            component_values[name] = result.value
            total += result.value * weight

        return LossResult(
            value=total,
            name=self.name,
            interpretation=f"Weighted loss={total:.4f} components: "
                           + ", ".join(f"{k}={v:.4f}*{self.weights.get(k, 0):.1f}" for k, v in component_values.items()),
            properties={"components": component_values, "weights": self.weights},
        )

    def gradient(self, predicted: float, actual: float) -> float:
        total_grad = 0.0
        for name, loss_fn in self.components.items():
            weight = self.weights.get(name, 0)
            if weight <= 0:
                continue
            total_grad += loss_fn.gradient(predicted, actual) * weight
        return total_grad

    def update_weights(self, new_weights: dict[str, float]):
        """Meta-agents can update weights to shift optimization focus."""
        self.weights.update(new_weights)


# Global registry of loss functions
LOSS_FUNCTIONS: dict[str, BaseLossFunction] = {
    "brier_score": BrierScore(),
    "log_loss": LogLoss(),
    "spherical_score": SphericalScore(),
    "calibration_loss": CalibrationLoss(),
}


def get_loss_function(name: str) -> BaseLossFunction:
    if name not in LOSS_FUNCTIONS:
        raise ValueError(f"Unknown loss function: {name}. Available: {list(LOSS_FUNCTIONS.keys())}")
    return LOSS_FUNCTIONS[name]
