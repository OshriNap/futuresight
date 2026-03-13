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


class BaseCollector(ABC):
    platform: str

    @abstractmethod
    async def collect(self) -> list[CollectedItem]:
        """Collect data from the source platform."""
        ...

    async def save_items(self, items: list[CollectedItem]) -> int:
        """Save collected items to the database."""
        from app.database import async_session
        from app.models.source import Source

        saved = 0
        async with async_session() as db:
            for item in items:
                # Check if already exists
                from sqlalchemy import select
                existing = await db.execute(
                    select(Source).where(
                        Source.platform == item.platform,
                        Source.external_id == item.external_id,
                    )
                )
                source = existing.scalar_one_or_none()
                if source:
                    # Update existing
                    source.title = item.title
                    source.description = item.description
                    source.current_market_probability = item.current_probability
                    source.raw_data = item.raw_data
                else:
                    # Create new
                    source = Source(
                        platform=item.platform,
                        external_id=item.external_id,
                        title=item.title,
                        description=item.description,
                        category=item.category,
                        current_market_probability=item.current_probability,
                        raw_data=item.raw_data,
                    )
                    db.add(source)
                    saved += 1
            await db.commit()
        return saved
