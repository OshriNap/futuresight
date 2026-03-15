"""Feature Ideator Meta-Agent

DEPRECATED: Thinking/brainstorming is now handled by Claude Code scheduled tasks.
This Python agent is kept only for backward compatibility with the trigger API.
It does minimal DB operations - all creative thinking happens in the scheduled task.
"""

import logging

from app.agents.meta.base_meta import BaseMetaAgent

logger = logging.getLogger(__name__)


class FeatureIdeator(BaseMetaAgent):
    agent_type = "feature_ideator"

    async def think(self) -> dict:
        return {
            "summary": "Feature ideation is handled by Claude Code scheduled tasks. "
                       "This Python agent is a no-op.",
            "actions": [],
            "scratchpad_entries": [],
        }
