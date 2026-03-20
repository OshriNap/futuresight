import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.database import async_session
from app.models.indicator import Indicator

logger = logging.getLogger(__name__)


@dataclass
class IndicatorRecord:
    source_agency: str
    series_id: str
    name: str
    category: str | None
    region: str | None
    value: float
    unit: str | None
    period: str
    release_date: date | None = None
    metadata: dict | None = None


class BaseIndicatorCollector(ABC):
    source_agency: str  # Must be set by subclass

    @abstractmethod
    async def _collect_impl(self, series_ids: list[str]) -> list[IndicatorRecord]:
        """Collect indicator data for the given series IDs. Subclasses implement this."""

    async def collect(self, series_ids: list[str]) -> list[IndicatorRecord]:
        """Collect with retry logic (3 attempts, exponential backoff)."""
        for attempt in range(3):
            try:
                return await self._collect_impl(series_ids)
            except Exception:
                if attempt == 2:
                    raise
                wait = 2 ** attempt
                logger.warning(f"{self.source_agency}: attempt {attempt + 1} failed, retrying in {wait}s")
                await asyncio.sleep(wait)
        return []  # unreachable, but satisfies type checker

    async def save_indicators(self, records: list[IndicatorRecord]) -> int:
        """Upsert indicator records. Returns count of new/updated records."""
        if not records:
            return 0

        saved = 0
        async with async_session() as session:
            for record in records:
                existing = await session.execute(
                    select(Indicator).where(
                        Indicator.source_agency == record.source_agency,
                        Indicator.series_id == record.series_id,
                        Indicator.period == record.period,
                    )
                )
                indicator = existing.scalar_one_or_none()

                if indicator:
                    if indicator.value != record.value:
                        indicator.value = record.value
                        indicator.release_date = record.release_date
                        indicator.metadata = record.metadata
                        flag_modified(indicator, "metadata")
                        saved += 1
                else:
                    indicator = Indicator(
                        source_agency=record.source_agency,
                        series_id=record.series_id,
                        name=record.name,
                        category=record.category,
                        region=record.region,
                        value=record.value,
                        unit=record.unit,
                        period=record.period,
                        release_date=record.release_date,
                        metadata=record.metadata,
                    )
                    session.add(indicator)
                    saved += 1

            await session.commit()

        logger.info(f"{self.source_agency}: saved {saved}/{len(records)} indicators")
        return saved
