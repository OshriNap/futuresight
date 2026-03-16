"""Evolution models — strategy genome versioning and A/B testing."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text, Uuid, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StrategyGenome(Base):
    """Versioned parameter set for prediction tools.

    Each genome contains ~40 tunable parameters that control tool behavior,
    plus NLI reframing strategies. Genomes compete via A/B testing on real
    predictions, with the best-performing genome promoted to champion.
    """
    __tablename__ = "strategy_genomes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    genome_data: Mapped[dict] = mapped_column(JSON)  # All tunable params
    reframe_strategies: Mapped[dict | None] = mapped_column(JSON)  # NLI reframing config
    fitness: Mapped[float | None] = mapped_column(Float)  # Avg Brier score (lower = better)
    status: Mapped[str] = mapped_column(String(30), default="candidate")  # active/candidate/retired/champion
    generation: Mapped[int] = mapped_column(Integer, default=0)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("strategy_genomes.id"))
    scored_predictions: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GenomePredictionLink(Base):
    """Maps which genome produced which prediction, for scoring."""
    __tablename__ = "genome_prediction_links"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    genome_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("strategy_genomes.id"), index=True)
    prediction_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("predictions.id"), index=True)
    reframe_variant: Mapped[str | None] = mapped_column(String(50))  # Which reframe strategy was used
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvolutionRun(Base):
    """Logs each evolution cycle for monitoring."""
    __tablename__ = "evolution_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    generation: Mapped[int] = mapped_column(Integer)
    candidates_created: Mapped[int] = mapped_column(Integer, default=0)
    candidates_retired: Mapped[int] = mapped_column(Integer, default=0)
    candidates_promoted: Mapped[int] = mapped_column(Integer, default=0)
    champion_fitness: Mapped[float | None] = mapped_column(Float)
    best_candidate_fitness: Mapped[float | None] = mapped_column(Float)
    improvement: Mapped[float | None] = mapped_column(Float)  # Fitness delta if promotion happened
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
