"""API endpoints for the scientific evaluation system."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.tools.evaluation.comparator import ToolComparator
from app.tools.evaluation.hypothesis_tester import HypothesisTester
from app.tools.loss_functions.registry import LOSS_FUNCTIONS, get_loss_function
from app.tools.tool_registry import registry as tool_registry

router = APIRouter()


class LossFunctionInfo(BaseModel):
    name: str
    description: str
    lower_is_better: bool
    range_min: float
    range_max: float


class LossFunctionCompute(BaseModel):
    predicted: float
    actual: float


class LossComputeResult(BaseModel):
    loss_name: str
    value: float
    interpretation: str
    gradient: float
    properties: dict


class ToolListResponse(BaseModel):
    name: str
    tool_type: str
    description: str
    best_for: list[str]
    requires_training: bool
    required_signals: list[str]


class HypothesisTestRequest(BaseModel):
    losses_a: list[float]
    losses_b: list[float]
    test_type: str = "paired_t"  # paired_t, sign


class CalibrationTestRequest(BaseModel):
    predictions: list[list[float]]  # [[predicted, actual], ...]
    n_bins: int = 10


class TrendTestRequest(BaseModel):
    values: list[float]


class TestResultResponse(BaseModel):
    test_type: str
    test_statistic: float
    p_value: float
    degrees_of_freedom: float | None
    is_significant_05: bool
    is_significant_01: bool
    effect_size: float | None
    interpretation: str
    details: dict


# --- Loss Functions ---

@router.get("/loss-functions", response_model=list[LossFunctionInfo])
async def list_loss_functions():
    """List all available loss functions with their properties."""
    return [
        LossFunctionInfo(
            name=name,
            description=fn.description,
            lower_is_better=fn.lower_is_better,
            range_min=fn.range[0],
            range_max=fn.range[1] if fn.range[1] != float("inf") else 999,
        )
        for name, fn in LOSS_FUNCTIONS.items()
    ]


@router.post("/loss-functions/{name}/compute", response_model=LossComputeResult)
async def compute_loss(name: str, data: LossFunctionCompute):
    """Compute a loss function for a single prediction."""
    fn = get_loss_function(name)
    result = fn.compute(data.predicted, data.actual)
    gradient = fn.gradient(data.predicted, data.actual)
    return LossComputeResult(
        loss_name=name,
        value=result.value,
        interpretation=result.interpretation,
        gradient=gradient,
        properties=result.properties,
    )


@router.post("/loss-functions/compare-all", response_model=list[LossComputeResult])
async def compare_all_losses(data: LossFunctionCompute):
    """Compute ALL loss functions for a prediction - see how different metrics evaluate it."""
    results = []
    for name, fn in LOSS_FUNCTIONS.items():
        result = fn.compute(data.predicted, data.actual)
        gradient = fn.gradient(data.predicted, data.actual)
        results.append(LossComputeResult(
            loss_name=name,
            value=result.value,
            interpretation=result.interpretation,
            gradient=gradient,
            properties=result.properties,
        ))
    return results


# --- Prediction Tools ---

@router.get("/tools", response_model=list[ToolListResponse])
async def list_prediction_tools():
    """List all registered prediction tools."""
    return [
        ToolListResponse(
            name=t.name,
            tool_type=t.tool_type,
            description=t.description,
            best_for=t.best_for,
            requires_training=t.requires_training,
            required_signals=t.get_required_signals(),
        )
        for t in tool_registry.list_tools()
    ]


# --- Hypothesis Testing ---

@router.post("/hypothesis/paired-test", response_model=TestResultResponse)
async def run_paired_test(data: HypothesisTestRequest):
    """Run a paired t-test or sign test comparing two tools' losses."""
    tester = HypothesisTester()
    if data.test_type == "sign":
        result = tester.sign_test(data.losses_a, data.losses_b)
    else:
        result = tester.paired_t_test(data.losses_a, data.losses_b)
    return TestResultResponse(
        test_type=result.test_type.value,
        test_statistic=result.test_statistic,
        p_value=result.p_value,
        degrees_of_freedom=result.degrees_of_freedom,
        is_significant_05=result.is_significant_05,
        is_significant_01=result.is_significant_01,
        effect_size=result.effect_size,
        interpretation=result.interpretation,
        details=result.details,
    )


@router.post("/hypothesis/calibration", response_model=TestResultResponse)
async def run_calibration_test(data: CalibrationTestRequest):
    """Run a chi-squared calibration test."""
    tester = HypothesisTester()
    predictions = [(p[0], p[1]) for p in data.predictions]
    result = tester.calibration_test(predictions, data.n_bins)
    return TestResultResponse(
        test_type=result.test_type.value,
        test_statistic=result.test_statistic,
        p_value=result.p_value,
        degrees_of_freedom=result.degrees_of_freedom,
        is_significant_05=result.is_significant_05,
        is_significant_01=result.is_significant_01,
        effect_size=result.effect_size,
        interpretation=result.interpretation,
        details=result.details,
    )


@router.post("/hypothesis/trend", response_model=TestResultResponse)
async def run_trend_test(data: TrendTestRequest):
    """Run a Mann-Kendall trend test to detect improvement or degradation."""
    tester = HypothesisTester()
    result = tester.trend_test(data.values)
    return TestResultResponse(
        test_type=result.test_type.value,
        test_statistic=result.test_statistic,
        p_value=result.p_value,
        degrees_of_freedom=result.degrees_of_freedom,
        is_significant_05=result.is_significant_05,
        is_significant_01=result.is_significant_01,
        effect_size=result.effect_size,
        interpretation=result.interpretation,
        details=result.details,
    )
