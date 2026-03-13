"""Base class for meta-agents - agents that think about and improve the system itself."""

import logging
import time
import uuid
from abc import ABC, abstractmethod

from app.database import async_session
from app.models.meta import MetaAgentRun, Scratchpad

logger = logging.getLogger(__name__)


class BaseMetaAgent(ABC):
    """Meta-agents observe, evaluate, and improve the prediction system.

    Unlike regular agents that collect data or make predictions,
    meta-agents reason about the system's performance and suggest improvements.
    """

    agent_type: str  # source_evaluator, strategy_optimizer, feature_ideator, method_researcher

    @abstractmethod
    async def think(self) -> dict:
        """Main thinking loop - analyze, evaluate, generate insights.

        Returns a dict with:
          - summary: str - what the agent thought about
          - actions: list[str] - actions taken
          - scratchpad_entries: list[dict] - new scratchpad entries to save
        """
        ...

    async def run(self) -> dict:
        """Execute the meta-agent and log the run."""
        start = time.time()
        result = await self.think()
        duration = time.time() - start

        async with async_session() as db:
            # Save scratchpad entries
            entries_created = 0
            for entry in result.get("scratchpad_entries", []):
                scratchpad = Scratchpad(
                    agent_type=self.agent_type,
                    title=entry["title"],
                    content=entry["content"],
                    category=entry.get("category", "insight"),
                    priority=entry.get("priority", "medium"),
                    tags=entry.get("tags"),
                    metadata=entry.get("metadata"),
                )
                db.add(scratchpad)
                entries_created += 1

            # Log the run
            run_log = MetaAgentRun(
                agent_type=self.agent_type,
                trigger="scheduled",
                input_summary=result.get("input_summary"),
                output_summary=result.get("summary", ""),
                actions_taken=result.get("actions", []),
                scratchpad_entries_created=entries_created,
                duration_seconds=duration,
            )
            db.add(run_log)
            await db.commit()

        logger.info(f"Meta-agent [{self.agent_type}] completed in {duration:.1f}s, {entries_created} scratchpad entries")
        return result

    async def read_scratchpad(self, category: str | None = None, limit: int = 50) -> list[Scratchpad]:
        """Read this agent's scratchpad entries."""
        from sqlalchemy import select

        async with async_session() as db:
            query = (
                select(Scratchpad)
                .where(Scratchpad.agent_type == self.agent_type)
                .where(Scratchpad.status == "active")
                .order_by(Scratchpad.created_at.desc())
                .limit(limit)
            )
            if category:
                query = query.where(Scratchpad.category == category)
            result = await db.execute(query)
            return result.scalars().all()
