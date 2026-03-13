"""Feature Ideator Meta-Agent

Creative agent that generates new ideas for improving the prediction system.

Responsibilities:
- Generate new feature ideas for predictions
- Propose new data sources to integrate
- Suggest system architecture improvements
- Think about novel prediction approaches
- Review and prioritize the backlog of ideas

This agent uses Claude to brainstorm based on the current system state.
"""

import logging

from sqlalchemy import func, select

from app.agents.meta.base_meta import BaseMetaAgent
from app.config import settings
from app.database import async_session
from app.models.meta import MetaAgentRun, Scratchpad
from app.models.prediction import Prediction, PredictionScore
from app.models.source import Source

logger = logging.getLogger(__name__)


class FeatureIdeator(BaseMetaAgent):
    agent_type = "feature_ideator"

    async def _get_system_context(self) -> str:
        """Build a summary of current system state for Claude to reason about."""
        async with async_session() as db:
            source_count = (await db.execute(select(func.count(Source.id)))).scalar() or 0
            pred_count = (await db.execute(select(func.count(Prediction.id)))).scalar() or 0
            avg_brier = (await db.execute(select(func.avg(PredictionScore.brier_score)))).scalar()

            # Get platforms
            platforms = await db.execute(select(Source.platform).distinct())
            platform_list = [r[0] for r in platforms.all()]

            # Get recent scratchpad entries from all agents
            recent_ideas = await db.execute(
                select(Scratchpad)
                .where(Scratchpad.status == "active")
                .order_by(Scratchpad.created_at.desc())
                .limit(20)
            )
            ideas = recent_ideas.scalars().all()

            # Recent meta-agent runs
            recent_runs = await db.execute(
                select(MetaAgentRun)
                .order_by(MetaAgentRun.created_at.desc())
                .limit(10)
            )
            runs = recent_runs.scalars().all()

        context = f"""Current system state:
- Total data sources: {source_count} items from platforms: {', '.join(platform_list)}
- Total predictions: {pred_count}
- Average Brier score: {f'{avg_brier:.4f}' if avg_brier else 'N/A (no scored predictions yet)'}

Recent scratchpad entries (what other meta-agents have noted):
"""
        for idea in ideas[:10]:
            context += f"\n- [{idea.category}] {idea.title}: {idea.content[:200]}"

        context += "\n\nRecent meta-agent activity:"
        for run in runs[:5]:
            context += f"\n- {run.agent_type}: {run.output_summary[:150]}"

        return context

    async def think(self) -> dict:
        entries = []
        actions = []

        context = await self._get_system_context()

        # If Anthropic API key is available, use Claude to brainstorm
        if settings.anthropic_api_key:
            try:
                import anthropic

                client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
                response = await client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    system="You are a meta-agent for a prediction platform. Your job is to generate creative, "
                           "actionable ideas for improving the system. Focus on practical improvements that can "
                           "be implemented. Output your ideas as a numbered list, each with a title and brief description.",
                    messages=[{
                        "role": "user",
                        "content": f"""Based on the current system state, generate 3-5 creative ideas for improving
our prediction accuracy, data collection, or system capabilities.

{context}

Focus on:
1. New data sources or signals we could integrate
2. Better prediction methods or ensemble strategies
3. Feature engineering ideas
4. System improvements (better calibration, faster feedback loops, etc.)
5. Novel approaches we haven't tried

Be specific and actionable. For each idea, explain WHY it would help.""",
                    }],
                )

                # Parse Claude's response into scratchpad entries
                ideas_text = response.content[0].text
                entries.append({
                    "title": "AI-generated improvement ideas",
                    "content": ideas_text,
                    "category": "idea",
                    "priority": "medium",
                    "tags": ["ai_generated", "brainstorm"],
                    "metadata": {"model": "claude-sonnet-4-20250514", "context_length": len(context)},
                })
                actions.append("Generated AI-powered improvement ideas")

            except Exception as e:
                logger.warning(f"Claude API call failed for brainstorming: {e}")
                entries.append({
                    "title": "Brainstorm fallback - manual idea generation",
                    "content": "Claude API unavailable. Manual brainstorm needed. "
                               "Consider: better news NLP, prediction market arbitrage detection, "
                               "temporal pattern mining, cross-category correlation analysis.",
                    "category": "idea",
                    "tags": ["fallback"],
                })
        else:
            # No API key - generate ideas from patterns
            entries.append({
                "title": "System improvement ideas (no AI)",
                "content": "Ideas based on system analysis:\n"
                           "1. Add RSS feed collector for real-time news monitoring\n"
                           "2. Implement probability change alerts\n"
                           "3. Build a prediction tournament between methods\n"
                           "4. Add Wikipedia current events as a source\n"
                           "5. Track prediction market volume spikes as early signals",
                "category": "idea",
                "priority": "medium",
                "tags": ["manual_brainstorm"],
            })

        # Review and prioritize old ideas
        old_ideas = await self.read_scratchpad(category="idea", limit=30)
        if len(old_ideas) > 20:
            entries.append({
                "title": "Idea backlog growing - needs prioritization",
                "content": f"There are {len(old_ideas)} active ideas in the scratchpad. "
                           "Consider reviewing and archiving low-priority ones, "
                           "or implementing the highest-value ones.",
                "category": "todo",
                "priority": "medium",
                "tags": ["backlog_management"],
            })

        return {
            "summary": f"Generated {len(entries)} new ideas/insights",
            "input_summary": context[:500],
            "actions": actions,
            "scratchpad_entries": entries,
        }
