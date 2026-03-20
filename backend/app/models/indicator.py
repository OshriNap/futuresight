import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Indicator(Base):
    __tablename__ = "indicators"
    __table_args__ = (
        UniqueConstraint("source_agency", "series_id", "period", name="uq_indicator_series_period"),
        Index("ix_indicator_series_release", "series_id", "release_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    source_agency: Mapped[str] = mapped_column(String(50), index=True)
    series_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(10), nullable=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    period: Mapped[str] = mapped_column(String(20))
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
