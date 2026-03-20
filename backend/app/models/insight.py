import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    domain: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(500))
    ground_truth: Mapped[str] = mapped_column(Text)
    trend_analysis: Mapped[str] = mapped_column(Text)
    prediction: Mapped[str] = mapped_column(Text)
    action_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[str] = mapped_column(String(20), default="medium")
    sources: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)
