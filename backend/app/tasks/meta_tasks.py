"""Meta-agent tasks - called via API endpoints."""

import logging

logger = logging.getLogger(__name__)


async def run_source_evaluator() -> dict:
    """Compute reliability scores per platform."""
    from app.agents.meta.source_evaluator import SourceEvaluator
    return await SourceEvaluator().run()


async def run_strategy_optimizer() -> dict:
    """Analyze calibration, tool performance, and confidence distribution."""
    from app.agents.meta.strategy_optimizer import StrategyOptimizer
    return await StrategyOptimizer().run()


async def run_method_researcher() -> dict:
    """Ensure prediction methods are registered in DB."""
    from app.agents.meta.method_researcher import MethodResearcher
    return await MethodResearcher().run()


async def run_feature_ideator() -> dict:
    """Analyze data quality, coverage gaps, and graph connectivity."""
    from app.agents.meta.feature_ideator import FeatureIdeator
    return await FeatureIdeator().run()
