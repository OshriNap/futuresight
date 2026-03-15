from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CollectedItem:
    platform: str
    external_id: str
    title: str
    description: str | None
    category: str | None
    current_probability: float | None
    resolution_date: str | None
    raw_data: dict
    signal_type: str = "news"  # market_probability, sentiment, engagement, news


class BaseCollector(ABC):
    platform: str

    @abstractmethod
    async def collect(self) -> list[CollectedItem]:
        """Collect data from the source platform."""
        ...

    async def save_items(self, items: list[CollectedItem]) -> int:
        """Save collected items to the database. Returns total upserted count."""
        from sqlalchemy import select

        from app.database import async_session
        from app.models.price_history import PriceSnapshot
        from app.models.source import Source

        saved = 0
        async with async_session() as db:
            for item in items:
                existing = await db.execute(
                    select(Source).where(
                        Source.platform == item.platform,
                        Source.external_id == item.external_id,
                    )
                )
                source = existing.scalar_one_or_none()
                if source:
                    source.title = item.title
                    source.description = item.description
                    source.current_market_probability = item.current_probability
                    source.signal_type = item.signal_type
                    source.raw_data = item.raw_data
                else:
                    source = Source(
                        platform=item.platform,
                        external_id=item.external_id,
                        title=item.title,
                        description=item.description,
                        category=item.category,
                        signal_type=item.signal_type,
                        current_market_probability=item.current_probability,
                        raw_data=item.raw_data,
                    )
                    db.add(source)

                # Record price snapshot for trend tracking
                if item.current_probability is not None:
                    await db.flush()  # ensure source.id is set
                    snapshot = PriceSnapshot(
                        source_id=source.id,
                        probability=item.current_probability,
                    )
                    db.add(snapshot)

                saved += 1
            await db.commit()
        return saved
