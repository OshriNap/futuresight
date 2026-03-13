"""Celery tasks for meta-agents."""

import asyncio

from app.tasks.celery_app import celery


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery.task(name="app.tasks.meta_tasks.run_source_evaluator")
def run_source_evaluator():
    from app.agents.meta.source_evaluator import SourceEvaluator
    return run_async(SourceEvaluator().run())


@celery.task(name="app.tasks.meta_tasks.run_strategy_optimizer")
def run_strategy_optimizer():
    from app.agents.meta.strategy_optimizer import StrategyOptimizer
    return run_async(StrategyOptimizer().run())


@celery.task(name="app.tasks.meta_tasks.run_method_researcher")
def run_method_researcher():
    from app.agents.meta.method_researcher import MethodResearcher
    return run_async(MethodResearcher().run())


@celery.task(name="app.tasks.meta_tasks.run_feature_ideator")
def run_feature_ideator():
    from app.agents.meta.feature_ideator import FeatureIdeator
    return run_async(FeatureIdeator().run())


@celery.task(name="app.tasks.meta_tasks.run_all_meta_agents")
def run_all_meta_agents():
    """Run all meta-agents in sequence."""
    results = {}
    results["source_evaluator"] = run_source_evaluator()
    results["strategy_optimizer"] = run_strategy_optimizer()
    results["method_researcher"] = run_method_researcher()
    results["feature_ideator"] = run_feature_ideator()
    return results
