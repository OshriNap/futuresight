"""Insight generation — produces layered analysis using local Ollama.

Generates draft insights (confidence: low) for each enabled interest.
Claude Code scheduled tasks can later replace these with high-quality analysis.
"""

import json
import logging

import httpx
from sqlalchemy import select, update

from app.database import async_session
from app.models.indicator import Indicator
from app.models.insight import Insight
from app.models.source import Source
from app.models.user_interest import UserInterest

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://192.168.50.114:11434"
OLLAMA_FAST = "qwen3:8b"        # Simple tasks, fast
OLLAMA_SMART = "qwen3.5:latest"  # Complex reasoning, slower

SYSTEM_PROMPT = """You are an economic and geopolitical analyst. Given data about a topic (indicators, market predictions, news), produce a structured analysis in valid JSON with these four fields:

{
  "ground_truth": "What the data actually says. Cite specific numbers, dates, sources. Be factual and precise.",
  "trend_analysis": "What patterns and trends are visible. Compare current values to historical. Note acceleration/deceleration.",
  "prediction": "What is likely to happen next based on the trends. Include timeframes and conditions.",
  "action_items": ["List of 2-4 specific, actionable considerations for someone tracking this domain."]
}

Rules:
- Be concise but specific. Every claim should reference data from the input.
- ground_truth is ONLY facts from the provided data, no speculation.
- trend_analysis connects the dots between data points.
- prediction is forward-looking but grounded in the trends.
- action_items should be practical and time-bound where possible.
- Respond with ONLY the JSON object, no markdown, no explanation."""


async def generate_insights() -> dict:
    """Generate draft insights for all enabled interests using Ollama."""
    async with async_session() as db:
        result = await db.execute(
            select(UserInterest).where(UserInterest.enabled.is_(True))
        )
        interests = result.scalars().all()

    if not interests:
        return {"generated": 0, "message": "No enabled interests"}

    generated = 0
    failed = 0
    results = {}

    for interest in interests:
        domain = interest.category or interest.name
        try:
            context = await _build_context(interest)
            if not context["has_data"]:
                results[domain] = "skipped — no data"
                continue

            analysis = await _call_ollama(context["prompt"])
            if not analysis:
                results[domain] = "ollama failed"
                failed += 1
                continue

            # Save insight
            async with async_session() as db:
                # Mark previous insights for this domain as stale
                await db.execute(
                    update(Insight)
                    .where(Insight.domain == domain, Insight.stale.is_(False))
                    .values(stale=True)
                )

                insight = Insight(
                    domain=domain,
                    title=analysis.get("title", f"{interest.name} — Auto Analysis"),
                    ground_truth=analysis.get("ground_truth", ""),
                    trend_analysis=analysis.get("trend_analysis", ""),
                    prediction=analysis.get("prediction", ""),
                    action_items=analysis.get("action_items", []),
                    confidence="low",
                    sources=context["source_refs"],
                )
                db.add(insight)
                await db.commit()

            results[domain] = "generated"
            generated += 1

        except Exception as e:
            logger.exception(f"Failed to generate insight for {domain}")
            results[domain] = f"error: {e}"
            failed += 1

    logger.info(f"Generated {generated} insights, {failed} failed")
    return {"generated": generated, "failed": failed, "details": results}


async def generate_single_insight(interest_id: str) -> dict:
    """Generate a draft insight for a single interest."""
    import uuid as uuid_mod
    async with async_session() as db:
        from sqlalchemy import select as sel
        result = await db.execute(
            sel(UserInterest).where(UserInterest.id == uuid_mod.UUID(interest_id))
        )
        interest = result.scalar_one_or_none()

    if not interest:
        return {"error": "Interest not found"}

    domain = interest.category or interest.name
    context = await _build_context(interest)
    if not context["has_data"]:
        return {"domain": domain, "status": "skipped — no data"}

    analysis = await _call_ollama(context["prompt"])
    if not analysis:
        return {"domain": domain, "status": "ollama failed"}

    async with async_session() as db:
        await db.execute(
            update(Insight)
            .where(Insight.domain == domain, Insight.stale.is_(False))
            .values(stale=True)
        )
        insight = Insight(
            domain=domain,
            title=analysis.get("title", f"{interest.name} — Auto Analysis"),
            ground_truth=analysis.get("ground_truth", ""),
            trend_analysis=analysis.get("trend_analysis", ""),
            prediction=analysis.get("prediction", ""),
            action_items=analysis.get("action_items", []),
            confidence="low",
            sources=context["source_refs"],
        )
        db.add(insight)
        await db.commit()

    return {"domain": domain, "status": "generated", "title": insight.title}


async def _build_context(interest: UserInterest) -> dict:
    """Build a text prompt with all available data for an interest."""
    parts = []
    source_refs = {"indicators": [], "market_sources": [], "news_sources": []}
    has_data = False

    async with async_session() as db:
        # Indicators
        indicator_ids = []
        for spec in interest.indicators or []:
            if ":" in spec:
                _, series_id = spec.split(":", 1)
                indicator_ids.append(series_id)

        if indicator_ids:
            ind_q = await db.execute(
                select(Indicator)
                .where(Indicator.series_id.in_(indicator_ids))
                .order_by(Indicator.release_date.desc())
                .limit(30)
            )
            indicators = ind_q.scalars().all()
            if indicators:
                has_data = True
                parts.append("## Economic Indicators")
                # Group by series
                by_series = {}
                for ind in indicators:
                    by_series.setdefault(ind.series_id, []).append(ind)
                for sid, points in by_series.items():
                    pts_str = ", ".join(f"{p.period}: {p.value:.2f}" for p in points[:5])
                    parts.append(f"- {points[0].name} ({points[0].unit}): {pts_str}")
                    source_refs["indicators"].append(sid)

        # Market sources
        keywords = (interest.keywords or []) + (interest.market_filters or [])
        if keywords:
            src_q = await db.execute(
                select(Source)
                .where(Source.signal_type == "market_probability")
                .where(Source.current_market_probability.isnot(None))
                .order_by(Source.updated_at.desc())
                .limit(300)
            )
            all_sources = src_q.scalars().all()
            markets = []
            for s in all_sources:
                title_lower = (s.title or "").lower()
                if any(k.lower() in title_lower for k in keywords):
                    markets.append(s)
                    if len(markets) >= 10:
                        break

            if markets:
                has_data = True
                parts.append("\n## Prediction Markets")
                for m in markets:
                    prob = m.current_market_probability
                    parts.append(f"- {m.title} — {prob:.0%} ({m.platform})")
                    source_refs["market_sources"].append(str(m.id))

        # News
        if keywords:
            news_q = await db.execute(
                select(Source)
                .where(Source.signal_type.in_(["news", "engagement"]))
                .order_by(Source.updated_at.desc())
                .limit(300)
            )
            all_news = news_q.scalars().all()
            news = []
            for s in all_news:
                title_lower = (s.title or "").lower()
                if any(k.lower() in title_lower for k in keywords):
                    news.append(s)
                    if len(news) >= 10:
                        break

            if news:
                has_data = True
                parts.append("\n## Recent News & Social")
                for n in news:
                    sentiment = (n.raw_data or {}).get("sentiment", {})
                    sent_str = f" [sentiment: {sentiment.get('label', '?')}]" if sentiment else ""
                    parts.append(f"- {n.title}{sent_str} ({n.platform})")
                    source_refs["news_sources"].append(str(n.id))

    prompt = f"# Analysis Request: {interest.name}\nRegion: {interest.region or 'Global'}\n\n"
    prompt += "\n".join(parts)
    prompt += "\n\nBased on this data, produce the structured JSON analysis."

    return {"prompt": prompt, "has_data": has_data, "source_refs": source_refs}


async def _call_ollama(prompt: str, model: str = OLLAMA_SMART) -> dict | None:
    """Call Ollama and parse JSON response."""
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "system": SYSTEM_PROMPT,
                    "prompt": "/no_think\n" + prompt,
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
            )
            resp.raise_for_status()
            text = resp.json().get("response", "")

            analysis = _extract_json(text)
            if not analysis:
                return None

            # Generate a title from ground_truth
            gt = analysis.get("ground_truth", "")
            title = gt[:80].split(". ")[0] if gt else "Auto-generated Analysis"
            analysis["title"] = title

            return analysis

    except Exception as e:
        logger.warning(f"Ollama call failed: {e}")
        return None


def _extract_json(text: str) -> dict | None:
    """Extract JSON from Ollama response, handling think tags, markdown, etc."""
    import re

    # Remove <think>...</think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Remove markdown code blocks
    if "```" in text:
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

    # Find first { ... last } as JSON
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    logger.warning(f"Could not extract JSON from Ollama response: {text[:300]}")
    return None
