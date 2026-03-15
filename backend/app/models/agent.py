import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    type: Mapped[str] = mapped_column(String(50))  # collector, analyst, predictor, graph_builder
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    config: Mapped[dict | None] = mapped_column(JSON)
    avg_brier_score: Mapped[float | None] = mapped_column(Float)
    total_predictions: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="agent")  # noqa: F821
    performance_logs: Mapped[list["AgentPerformanceLog"]] = relationship(back_populates="agent")


class AgentPerformanceLog(Base):
    __tablename__ = "agent_performance_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    brier_score: Mapped[float] = mapped_column(Float)
    calibration_error: Mapped[float | None] = mapped_column(Float)
    prediction_count: Mapped[int] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(100))
    improvement_notes: Mapped[str | None] = mapped_column(Text)

    agent: Mapped["Agent"] = relationship(back_populates="performance_logs")
