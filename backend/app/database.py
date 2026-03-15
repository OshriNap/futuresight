import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Ensure the data directory exists for SQLite
if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.split("///", 1)[1]
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def create_tables():
    """Create all tables (used instead of Alembic for SQLite dev)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
