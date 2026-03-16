"""Evolution engine — genome management, mutation, evaluation, and promotion."""

import logging
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.evolution.defaults import DEFAULT_GENOME, DEFAULT_REFRAMES, MUTATION_RANGES
from app.models.evolution import EvolutionRun, GenomePredictionLink, StrategyGenome
from app.models.prediction import PredictionScore

logger = logging.getLogger(__name__)

# Minimum scored predictions before evaluating a candidate
MIN_SCORED = 15
# Candidate must beat champion by this much (Brier) to promote
PROMOTION_THRESHOLD = 0.005
# Retire candidate if worse than champion by this much
RETIREMENT_THRESHOLD = 0.01


class EvolutionEngine:
    """Manages the lifecycle of strategy genomes."""

    async def get_champion(self, db: AsyncSession | None = None) -> StrategyGenome | None:
        """Get the current champion genome."""
        async def _query(session: AsyncSession):
            result = await session.execute(
                select(StrategyGenome).where(StrategyGenome.status == "champion")
            )
            return result.scalar_one_or_none()

        if db:
            return await _query(db)
        async with async_session() as session:
            return await _query(session)

    async def get_active_genomes(self, db: AsyncSession | None = None) -> list[StrategyGenome]:
        """Get champion + all active candidates."""
        async def _query(session: AsyncSession):
            result = await session.execute(
                select(StrategyGenome).where(
                    StrategyGenome.status.in_(["champion", "candidate"])
                )
            )
            return list(result.scalars().all())

        if db:
            return await _query(db)
        async with async_session() as session:
            return await _query(session)

    async def ensure_champion(self, db: AsyncSession) -> StrategyGenome:
        """Ensure a champion genome exists. Creates generation 0 if needed."""
        champion = await self.get_champion(db)
        if champion:
            return champion

        champion = StrategyGenome(
            genome_data=dict(DEFAULT_GENOME),
            reframe_strategies=dict(DEFAULT_REFRAMES),
            fitness=None,
            status="champion",
            generation=0,
            parent_id=None,
            notes="Generation 0 — all default parameters",
        )
        db.add(champion)
        await db.flush()
        logger.info(f"Created champion genome (gen 0): {champion.id}")
        return champion

    def assign_genome(self, genomes: list[StrategyGenome]) -> StrategyGenome:
        """Assign a genome for a prediction: 70% champion, 10% each candidate.

        Args:
            genomes: List of active genomes (champion + candidates)

        Returns:
            Selected genome
        """
        if not genomes:
            raise ValueError("No active genomes")

        champion = next((g for g in genomes if g.status == "champion"), None)
        candidates = [g for g in genomes if g.status == "candidate"]

        if not champion:
            return genomes[0]

        if not candidates:
            return champion

        # 70% champion, remaining split equally among candidates
        roll = random.random()
        if roll < 0.70 or not candidates:
            return champion

        # 30% split among candidates equally
        idx = int((roll - 0.70) / 0.30 * len(candidates))
        idx = min(idx, len(candidates) - 1)
        return candidates[idx]

    def mutate(self, genome: StrategyGenome, n_params: int | None = None) -> dict:
        """Create a mutated copy of genome_data.

        Args:
            genome: Parent genome to mutate
            n_params: Number of parameters to mutate (default: random 2-5)

        Returns:
            New genome_data dict with mutations applied
        """
        data = dict(genome.genome_data)
        if n_params is None:
            n_params = random.randint(2, 5)

        # Pick random parameters to mutate
        mutable_keys = [k for k in data if k in MUTATION_RANGES]
        if not mutable_keys:
            return data

        keys_to_mutate = random.sample(mutable_keys, min(n_params, len(mutable_keys)))

        for key in keys_to_mutate:
            min_val, max_val, sigma = MUTATION_RANGES[key]
            current = data[key]
            # Gaussian noise
            noise = random.gauss(0, sigma)
            new_val = current + noise
            # Clamp to range
            new_val = max(min_val, min(max_val, new_val))
            # Round integers
            if isinstance(DEFAULT_GENOME.get(key), int):
                new_val = int(round(new_val))
            else:
                new_val = round(new_val, 6)
            data[key] = new_val

        return data

    def mutate_reframes(self, reframes: dict | None) -> dict:
        """Mutate reframing strategy weights."""
        if not reframes:
            reframes = dict(DEFAULT_REFRAMES)
        else:
            reframes = {k: dict(v) for k, v in reframes.items()}

        # Mutate 1-2 strategy weights
        strategies = list(reframes.keys())
        n = random.randint(1, min(2, len(strategies)))
        for key in random.sample(strategies, n):
            current_weight = reframes[key].get("weight", 0.0)
            noise = random.gauss(0, 0.15)
            new_weight = max(0.0, min(1.0, current_weight + noise))
            reframes[key]["weight"] = round(new_weight, 3)

        return reframes

    async def evaluate_genomes(self) -> dict:
        """Evaluate all candidates against the champion.

        Computes average Brier score for each genome's predictions.
        Promotes/retires candidates that have enough scored predictions.

        Returns:
            Summary of evaluation results
        """
        async with async_session() as db:
            champion = await self.ensure_champion(db)

            # Get all candidates
            result = await db.execute(
                select(StrategyGenome).where(StrategyGenome.status == "candidate")
            )
            candidates = list(result.scalars().all())

            if not candidates:
                await db.commit()
                return {"status": "no_candidates", "champion_fitness": champion.fitness}

            # Compute fitness for champion
            champion_fitness = await self._compute_fitness(db, champion.id)
            if champion_fitness is not None:
                champion.fitness = champion_fitness
                champion.scored_predictions = await self._count_scored(db, champion.id)

            promoted = []
            retired = []

            for candidate in candidates:
                fitness = await self._compute_fitness(db, candidate.id)
                scored = await self._count_scored(db, candidate.id)
                candidate.scored_predictions = scored

                if fitness is not None:
                    candidate.fitness = fitness

                if scored < MIN_SCORED:
                    continue  # Not enough data yet

                if fitness is None:
                    continue

                if champion_fitness is not None:
                    improvement = champion_fitness - fitness  # Lower Brier = better
                    if improvement > PROMOTION_THRESHOLD:
                        # Promote this candidate to champion
                        champion.status = "retired"
                        champion.notes = (
                            f"Retired: beaten by gen {candidate.generation} "
                            f"(Brier {champion_fitness:.4f} → {fitness:.4f})"
                        )
                        candidate.status = "champion"
                        candidate.notes = (
                            f"Promoted from candidate. "
                            f"Improvement: {improvement:.4f} Brier over gen {champion.generation}"
                        )
                        promoted.append(str(candidate.id))
                        champion = candidate  # Update reference
                        logger.info(
                            f"Promoted genome {candidate.id} (gen {candidate.generation}): "
                            f"Brier {fitness:.4f} beats {champion_fitness:.4f}"
                        )
                    elif fitness - champion_fitness > RETIREMENT_THRESHOLD:
                        # Retire underperformer
                        candidate.status = "retired"
                        candidate.notes = f"Retired: worse than champion by {fitness - champion_fitness:.4f}"
                        retired.append(str(candidate.id))
                else:
                    # No champion fitness yet — if candidate has data, it becomes the benchmark
                    pass

            await db.commit()

            return {
                "champion_id": str(champion.id),
                "champion_fitness": champion.fitness,
                "promoted": promoted,
                "retired": retired,
                "candidates_remaining": len(candidates) - len(promoted) - len(retired),
            }

    async def create_candidates(self, n: int = 3) -> list[str]:
        """Create n new candidate genomes by mutating the champion.

        Uses LLM-guided mutation for the first candidate (when history is available),
        then random mutation for the rest. This gives us 1 "smart" candidate + 2
        exploratory candidates per generation.

        Returns:
            List of new genome IDs
        """
        async with async_session() as db:
            champion = await self.ensure_champion(db)

            # Check how many active candidates exist
            result = await db.execute(
                select(func.count(StrategyGenome.id)).where(
                    StrategyGenome.status == "candidate"
                )
            )
            existing = result.scalar() or 0

            # Don't create more than 3 total candidates
            to_create = max(0, n - existing)
            if to_create == 0:
                await db.commit()
                return []

            # Try to get LLM-guided mutations for the first candidate
            llm_mutations = None
            if champion.fitness is not None:
                llm_mutations = await self._get_llm_guided_mutations(db, champion)

            new_ids = []
            for i in range(to_create):
                # First candidate: use LLM guidance if available
                if i == 0 and llm_mutations:
                    from app.evolution.llm_advisor import apply_guided_mutations
                    mutated_data = apply_guided_mutations(champion.genome_data, llm_mutations)
                    mutation_source = "llm_guided"
                    reasons = "; ".join(m["reason"][:60] for m in llm_mutations[:3])
                    note = f"LLM-guided mutation from gen {champion.generation}: {reasons}"
                else:
                    mutated_data = self.mutate(champion)
                    mutation_source = "random"
                    note = f"Random mutation from champion gen {champion.generation}"

                mutated_reframes = self.mutate_reframes(champion.reframe_strategies)

                candidate = StrategyGenome(
                    genome_data=mutated_data,
                    reframe_strategies=mutated_reframes,
                    fitness=None,
                    status="candidate",
                    generation=champion.generation + 1,
                    parent_id=champion.id,
                    notes=note,
                )
                db.add(candidate)
                await db.flush()
                new_ids.append(str(candidate.id))
                logger.info(f"Created {mutation_source} candidate {candidate.id}")

            await db.commit()
            logger.info(f"Created {len(new_ids)} candidate genomes (gen {champion.generation + 1})")
            return new_ids

    async def _get_llm_guided_mutations(
        self, db: AsyncSession, champion: StrategyGenome
    ) -> list[dict] | None:
        """Try to get LLM-guided mutations. Returns None if unavailable."""
        try:
            from app.evolution.llm_advisor import propose_guided_mutations

            # Gather history
            result = await db.execute(
                select(EvolutionRun).order_by(EvolutionRun.created_at.desc()).limit(10)
            )
            history = [
                {
                    "generation": r.generation,
                    "champion_fitness": r.champion_fitness,
                    "candidates_created": r.candidates_created,
                    "candidates_retired": r.candidates_retired,
                    "candidates_promoted": r.candidates_promoted,
                }
                for r in result.scalars().all()
            ]

            # Gather retired genomes
            result = await db.execute(
                select(StrategyGenome)
                .where(StrategyGenome.status == "retired")
                .order_by(StrategyGenome.created_at.desc())
                .limit(5)
            )
            retired = [
                {
                    "generation": g.generation,
                    "fitness": g.fitness,
                    "genome_data": g.genome_data,
                }
                for g in result.scalars().all()
            ]

            mutations = await propose_guided_mutations(
                champion_data=champion.genome_data,
                champion_fitness=champion.fitness,
                history=history,
                retired_genomes=retired,
            )
            if mutations:
                logger.info(f"LLM proposed {len(mutations)} mutations: "
                           f"{[m['param'] for m in mutations]}")
            return mutations

        except Exception as e:
            logger.warning(f"LLM-guided mutation unavailable: {e}")
            return None

    async def _compute_fitness(self, db: AsyncSession, genome_id: uuid.UUID) -> float | None:
        """Compute average Brier score for a genome's predictions."""
        result = await db.execute(
            select(func.avg(PredictionScore.brier_score))
            .join(GenomePredictionLink, GenomePredictionLink.prediction_id == PredictionScore.prediction_id)
            .where(GenomePredictionLink.genome_id == genome_id)
        )
        avg = result.scalar()
        return round(avg, 6) if avg is not None else None

    async def _count_scored(self, db: AsyncSession, genome_id: uuid.UUID) -> int:
        """Count how many scored predictions this genome has."""
        result = await db.execute(
            select(func.count(PredictionScore.id))
            .join(GenomePredictionLink, GenomePredictionLink.prediction_id == PredictionScore.prediction_id)
            .where(GenomePredictionLink.genome_id == genome_id)
        )
        return result.scalar() or 0


# Global engine instance
evolution_engine = EvolutionEngine()
