"""Evolution tasks — orchestrates genome evaluation and candidate creation.

LLM integration:
- Guided mutation: local Ollama qwen2.5-coder (called inline by EvolutionEngine)
- Meta-analysis: handled externally by Claude Code scheduled task via REST API
"""

import logging

from app.database import async_session
from app.evolution.engine import evolution_engine
from app.models.evolution import EvolutionRun

logger = logging.getLogger(__name__)


async def run_evolution_cycle() -> dict:
    """Full evolution cycle: evaluate existing candidates, retire losers, create new ones.

    Called as a post-hook after score_predictions() resolves markets.
    First candidate uses LLM-guided mutation (Ollama) if available, rest use random.
    """
    # Step 1: Evaluate candidates against champion
    eval_result = await evolution_engine.evaluate_genomes()
    logger.info(f"Evolution evaluation: {eval_result}")

    # Step 2: Create new candidates if needed (maintain 3 active candidates)
    # First candidate will use LLM-guided mutation if Ollama is available
    new_ids = await evolution_engine.create_candidates(n=3)

    # Step 3: Log the evolution run
    champion = await evolution_engine.get_champion()
    generation = champion.generation if champion else 0

    async with async_session() as db:
        run = EvolutionRun(
            generation=generation,
            candidates_created=len(new_ids),
            candidates_retired=len(eval_result.get("retired", [])),
            candidates_promoted=len(eval_result.get("promoted", [])),
            champion_fitness=eval_result.get("champion_fitness"),
            best_candidate_fitness=None,
            improvement=None,
            details={
                "eval": eval_result,
                "new_candidates": new_ids,
            },
        )
        db.add(run)
        await db.commit()

    return {
        "evaluation": eval_result,
        "new_candidates": new_ids,
        "generation": generation,
    }
