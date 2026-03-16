"""Base class for prediction tools.

A "tool" is a specific prediction method that agents can invoke.
Each tool knows how to take input signals and produce a probability estimate.
Tools track their own performance so the system learns which tool to use when.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ToolInput:
    """Standard input to a prediction tool."""
    question: str  # What are we predicting?
    category: str  # geopolitical, economic, tech, etc.
    current_signals: dict  # Available data signals
    historical_data: list[dict] | None = None  # Past similar predictions
    time_horizon: str = "medium"  # short, medium, long
    metadata: dict = field(default_factory=dict)
    genome_params: dict | None = None  # Evolved parameters from StrategyGenome


@dataclass
class ToolOutput:
    """Standard output from a prediction tool."""
    probability: float  # 0.0 - 1.0
    confidence: float  # How confident is the tool in its own estimate
    reasoning: str  # Explanation
    signals_used: list[str]  # Which input signals were actually used
    metadata: dict = field(default_factory=dict)


class BasePredictionTool(ABC):
    """Abstract base for all prediction tools.

    Each tool is a specific method for generating predictions.
    Tools are registered in the PredictionMethod table and track performance.
    """

    name: str
    tool_type: str  # statistical, ml_classifier, ml_regressor, llm_reasoning, ensemble, heuristic
    description: str
    best_for: list[str]  # Categories this tool excels at
    requires_training: bool = False  # Whether this tool needs training data

    @abstractmethod
    async def predict(self, input: ToolInput) -> ToolOutput:
        """Generate a prediction given the input signals."""
        ...

    @abstractmethod
    def get_required_signals(self) -> list[str]:
        """List of signal names this tool needs to function."""
        ...

    def can_handle(self, input: ToolInput) -> tuple[bool, str]:
        """Check if this tool can handle the given input.
        Returns (can_handle: bool, reason: str).
        """
        required = set(self.get_required_signals())
        available = set(input.current_signals.keys())
        missing = required - available
        if missing:
            return False, f"Missing signals: {', '.join(missing)}"
        return True, "ok"
