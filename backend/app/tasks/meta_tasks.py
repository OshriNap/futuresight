"""Meta-agent tasks - called via API endpoints.

All analytical thinking is handled by Claude Code scheduled tasks.
These tasks only do mechanical DB operations (reliability scoring, method registration).
"""

import logging

logger = logging.getLogger(__name__)


async def run_source_evaluator() -> dict:
    """Compute reliability scores (DB-only, no thinking)."""
    from app.agents.meta.source_evaluator import SourceEvaluator
    return await SourceEvaluator().run()


async def run_strategy_optimizer() -> dict:
    """No-op. Strategy analysis handled by Claude Code scheduled tasks."""
    from app.agents.meta.strategy_optimizer import StrategyOptimizer
    return await StrategyOptimizer().run()


async def run_method_researcher() -> dict:
    """Ensure prediction methods are registered in DB."""
    from app.agents.meta.method_researcher import MethodResearcher
    return await MethodResearcher().run()
