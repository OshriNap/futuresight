"""Evolve prediction ensemble using evolution-agent framework.

Uses the evolution-agent's EvolutionEngine to evolve the ensemble_and_adjust()
function — the core logic that takes tool outputs and produces a final probability.
Fitness = negative avg Brier score on resolved markets (lower Brier = higher fitness).

Usage:
    cd backend
    .venv/bin/python evolve_tools.py [--generations 30] [--population 8]
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import sys
from pathlib import Path

# Evolution agent imports
from evolution_agent.core.config import load_config
from evolution_agent.core.engine import EvolutionEngine
from evolution_agent.core.types import EvalResult, OptimizationDirection
from evolution_agent.evaluation.base import BaseEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolved dataset — built once, reused for every fitness evaluation
# ---------------------------------------------------------------------------

_DATASET: list[dict] | None = None


async def _build_dataset() -> list[dict]:
    """Load resolved markets with signals + actual outcomes."""
    from app.database import async_session
    from app.tasks.evolution_backtest import _build_resolved_dataset

    async with async_session() as db:
        return await _build_resolved_dataset(db)


# ---------------------------------------------------------------------------
# Seed code — the current ensemble_and_adjust function
# ---------------------------------------------------------------------------

FUNCTION_NAME = "ensemble_and_adjust"

FUNCTION_SPEC = '''\
def ensemble_and_adjust(tool_results: list[dict], category: str, time_horizon: str) -> float:
    """Combine multiple prediction tool outputs into a final probability.

    Args:
        tool_results: List of dicts, each with:
            - "probability": float (0-1), the tool's predicted probability
            - "confidence": float (0-1), how confident the tool is
            - "weight": float, pre-computed weight (confidence * performance)
            - "tool_name": str
        category: Prediction category (politics, finance, technology, etc.)
        time_horizon: "short", "medium", or "long"

    Returns:
        Final probability as a float in [0.02, 0.98].

    Available in scope: math (module), log, exp, sqrt.
    """
'''

SEED_CODE = '''\
def ensemble_and_adjust(tool_results, category, time_horizon):
    """Log-linear pooling with dynamic extremization."""
    if not tool_results:
        return 0.5
    if len(tool_results) == 1:
        return max(0.02, min(0.98, tool_results[0]["probability"]))

    total_weight = sum(r["weight"] for r in tool_results)
    if total_weight == 0:
        total_weight = len(tool_results)
        for r in tool_results:
            r["weight"] = 1.0

    # Log-linear pooling in log-odds space
    log_odds_sum = 0.0
    for r in tool_results:
        p = max(0.01, min(0.99, r["probability"]))
        norm_weight = r["weight"] / total_weight
        log_odds_sum += norm_weight * log(p / (1 - p))

    weighted_prob = 1.0 / (1.0 + exp(-log_odds_sum))

    # Dynamic extremization based on tool agreement
    probs = [r["probability"] for r in tool_results]
    mean_prob = sum(probs) / len(probs)
    variance = sum((p - mean_prob) ** 2 for p in probs) / len(probs)
    agreement = 1.0 - min(1.0, variance / 0.06)
    extremize_factor = 1.0 + 0.35 * agreement

    lo = log(weighted_prob / (1 - weighted_prob))
    extremized = 1.0 / (1.0 + exp(-lo * extremize_factor))

    return max(0.02, min(0.98, extremized))
'''


# ---------------------------------------------------------------------------
# Custom evaluator — runs evolved function on resolved dataset
# ---------------------------------------------------------------------------

class PredictionEvaluator(BaseEvaluator):
    """Evaluate an ensemble function by running it on resolved market data."""

    def __init__(self, dataset: list[dict], timeout_s: float = 30.0):
        self._dataset = dataset
        self._timeout_s = timeout_s

    async def evaluate(self, code: str) -> EvalResult:
        """Compile and run the evolved function against the dataset."""
        import time
        t0 = time.monotonic()

        # Compile the function
        safe_globals = {
            "__builtins__": {
                "abs": abs, "max": max, "min": min, "sum": sum, "len": len,
                "sorted": sorted, "enumerate": enumerate, "range": range,
                "zip": zip, "round": round, "float": float, "int": int,
                "str": str, "bool": bool, "list": list, "dict": dict,
                "tuple": tuple, "set": set, "True": True, "False": False,
                "None": None, "isinstance": isinstance, "any": any, "all": all,
                "map": map, "filter": filter, "pow": pow,
            },
            "math": math,
            "log": math.log,
            "exp": math.exp,
            "sqrt": math.sqrt,
        }

        try:
            exec(code, safe_globals)
        except Exception as e:
            return EvalResult(
                fitness=self.worst_fitness(),
                error=f"Compilation failed: {e}",
                eval_time_s=time.monotonic() - t0,
            )

        fn = safe_globals.get(FUNCTION_NAME)
        if fn is None:
            return EvalResult(
                fitness=self.worst_fitness(),
                error=f"Function '{FUNCTION_NAME}' not found in code",
                eval_time_s=time.monotonic() - t0,
            )

        # Run the function on the dataset via the real tool pipeline
        from app.tools.base_tool import ToolInput
        from app.tools.tool_registry import registry

        try:
            perf_data = await _load_performance_data()
        except Exception:
            perf_data = None

        brier_scores = []
        errors = 0

        for item in self._dataset:
            try:
                tool_input = ToolInput(
                    question=item["title"],
                    category=item["category"],
                    current_signals=item["signals"],
                    time_horizon=item["time_horizon"],
                    metadata=item["metadata"],
                )

                tool_names = registry.select_tools(tool_input, perf_data)
                results = await registry.run_tools(tool_input, tool_names, perf_data)

                if not results:
                    continue

                # Build the input format for the evolved function
                tool_dicts = [
                    {
                        "probability": r.output.probability,
                        "confidence": r.output.confidence,
                        "weight": r.weight,
                        "tool_name": r.tool_name,
                    }
                    for r in results
                ]

                # Call the evolved ensemble function
                prob = fn(tool_dicts, item["category"], item["time_horizon"])
                prob = max(0.02, min(0.98, float(prob)))

                brier = (prob - item["actual"]) ** 2
                brier_scores.append(brier)

            except Exception as e:
                errors += 1
                if errors > 5:
                    return EvalResult(
                        fitness=self.worst_fitness(),
                        error=f"Too many runtime errors: {e}",
                        eval_time_s=time.monotonic() - t0,
                    )

        if not brier_scores:
            return EvalResult(
                fitness=self.worst_fitness(),
                error="No predictions evaluated",
                eval_time_s=time.monotonic() - t0,
            )

        avg_brier = sum(brier_scores) / len(brier_scores)

        # Fitness = negative Brier (we MAXIMIZE, so lower Brier = higher fitness)
        fitness = -avg_brier

        return EvalResult(
            fitness=round(fitness, 6),
            metrics={
                "avg_brier": round(avg_brier, 6),
                "scored": len(brier_scores),
                "errors": errors,
            },
            eval_time_s=time.monotonic() - t0,
        )

    def get_direction(self) -> OptimizationDirection:
        return OptimizationDirection.MAXIMIZE

    def worst_fitness(self) -> float:
        return -1.0  # Worst possible Brier is 1.0, so -1.0

    def get_function_spec(self) -> str:
        return FUNCTION_SPEC


async def _load_performance_data():
    from app.tasks.scoring_tasks import build_performance_data
    return await build_performance_data()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Evolve prediction ensemble function")
    parser.add_argument("--generations", type=int, default=20)
    parser.add_argument("--population", type=int, default=8)
    parser.add_argument("--analyzer-every", type=int, default=5)
    args = parser.parse_args()

    # Build dataset
    logger.info("Building resolved market dataset...")
    dataset = await _build_dataset()
    logger.info(f"Dataset: {len(dataset)} resolved markets")

    if not dataset:
        logger.error("No resolved markets found. Run the pipeline first.")
        return

    config = load_config(
        str(Path("/home/oshrin/projects/evolution-agent/config/default.yaml")),
        overrides={
            "population_size": args.population,
            "max_generations": args.generations,
            "elite_count": 2,
            "analyzer_every_n_gens": args.analyzer_every,
            "stagnation_limit": 10,
            "ollama_base_url": "http://192.168.50.114:11434",
            "mutator_model": "qwen2.5:7b",
            "analyzer_model": "claude-code",
            "meta_optimizer_type": "heuristic",
            "direction": "maximize",
            "eval_timeout_s": 60.0,
            "log_dir": str(Path(__file__).parent / "evolution_runs"),
            "max_concurrent_evals": 1,  # Sequential — tools share GPU
            "max_concurrent_mutations": 4,
        },
    )

    evaluator = PredictionEvaluator(dataset=dataset, timeout_s=60.0)

    engine = EvolutionEngine(
        config=config,
        evaluator=evaluator,
        seeds=[SEED_CODE],
    )

    logger.info(f"Starting evolution: {args.generations} generations, population {args.population}")
    summary = await engine.run()

    print("\n" + "=" * 60)
    print("EVOLUTION COMPLETE")
    print("=" * 60)
    print(f"Generations: {summary['total_generations']}")
    print(f"Best fitness: {summary['best_fitness']:.6f} (Brier: {-summary['best_fitness']:.6f})")
    print(f"Elapsed: {summary['elapsed_s']:.1f}s")
    print(f"\nBest ensemble code:")
    print("-" * 40)
    print(summary.get("best_code", "N/A"))


if __name__ == "__main__":
    asyncio.run(main())
