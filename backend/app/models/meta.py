import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SourceReliability(Base):
    """Tracks reliability scores for each data source over time."""
    __tablename__ = "source_reliability"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(50), index=True)
    reliability_score: Mapped[float] = mapped_column(Float)  # 0-1
    accuracy_rate: Mapped[float | None] = mapped_column(Float)  # % of correct resolutions
    timeliness_score: Mapped[float | None] = mapped_column(Float)  # how fast it provides data
    coverage_score: Mapped[float | None] = mapped_column(Float)  # breadth of topics
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Scratchpad(Base):
    """Meta-agent scratchpad - persistent notes on what works, what doesn't, ideas."""
    __tablename__ = "scratchpads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_type: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))  # insight, idea, failure, success, experiment, todo
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="active")  # active, implemented, rejected, archived
    tags: Mapped[list | None] = mapped_column(JSON)
    extra_data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PredictionMethod(Base):
    """Registry of prediction methods/tools available to the system."""
    __tablename__ = "prediction_methods"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    method_type: Mapped[str] = mapped_column(String(50))  # statistical, ml_model, ensemble, heuristic, llm_reasoning
    description: Mapped[str] = mapped_column(Text)
    config: Mapped[dict | None] = mapped_column(JSON)  # method-specific config
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    avg_accuracy: Mapped[float | None] = mapped_column(Float)
    best_categories: Mapped[list | None] = mapped_column(JSON)  # categories where this method excels
    worst_categories: Mapped[list | None] = mapped_column(JSON)
    total_uses: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FeatureImportance(Base):
    """Tracks which features/signals are most useful for predictions."""
    __tablename__ = "feature_importance"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    feature_name: Mapped[str] = mapped_column(String(200))
    feature_source: Mapped[str] = mapped_column(String(100))  # polymarket, news_sentiment, volume, etc.
    category: Mapped[str | None] = mapped_column(String(100))  # which prediction category
    importance_score: Mapped[float] = mapped_column(Float)  # 0-1
    correlation_with_accuracy: Mapped[float | None] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PredictionPattern(Base):
    """Persistent pattern library — validated patterns that persist across prediction runs.

    Inspired by openevolve's MetaPatternLibrary. Stores patterns like
    "sentiment divergence > 0.15 predicts market correction" with validation stats.
    """
    __tablename__ = "prediction_patterns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(300))
    pattern_type: Mapped[str] = mapped_column(String(50))  # signal_pattern, calibration, tool_interaction, category_bias
    description: Mapped[str] = mapped_column(Text)
    condition: Mapped[dict] = mapped_column(JSON)  # Machine-readable pattern definition
    # e.g. {"type": "sentiment_divergence", "threshold": 0.15, "direction": "above", "signal": "correction"}
    times_seen: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float | None] = mapped_column(Float)  # times_correct / times_seen
    avg_impact: Mapped[float | None] = mapped_column(Float)  # avg Brier improvement when pattern applied
    status: Mapped[str] = mapped_column(String(30), default="candidate")  # candidate, validated, rejected, retired
    discovered_by: Mapped[str] = mapped_column(String(50))  # which agent/process found it
    category: Mapped[str | None] = mapped_column(String(100))  # which prediction category, or null for global
    version: Mapped[int] = mapped_column(Integer, default=1)  # incremented on updates
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MetaAgentRun(Base):
    """Log of meta-agent execution runs and their outputs."""
    __tablename__ = "meta_agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_type: Mapped[str] = mapped_column(String(50), index=True)
    trigger: Mapped[str] = mapped_column(String(50))  # scheduled, manual, event
    input_summary: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[str] = mapped_column(Text)
    actions_taken: Mapped[list | None] = mapped_column(JSON)
    scratchpad_entries_created: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
