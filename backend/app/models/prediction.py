import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"))
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"))
    prediction_text: Mapped[str] = mapped_column(Text)
    predicted_outcome: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float)  # 0.0 - 1.0
    reasoning: Mapped[str | None] = mapped_column(Text)
    time_horizon: Mapped[str] = mapped_column(String(20))  # short, medium, long
    data_signals: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source: Mapped["Source"] = relationship(back_populates="predictions")  # noqa: F821
    agent: Mapped["Agent"] = relationship(back_populates="predictions")  # noqa: F821
    scores: Mapped[list["PredictionScore"]] = relationship(back_populates="prediction")


class PredictionScore(Base):
    __tablename__ = "prediction_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prediction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("predictions.id"))
    brier_score: Mapped[float] = mapped_column(Float)
    calibration_error: Mapped[float | None] = mapped_column(Float)
    absolute_error: Mapped[float | None] = mapped_column(Float)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    prediction: Mapped["Prediction"] = relationship(back_populates="scores")
