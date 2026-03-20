"""Categorization — classifies sources using Ollama LLM.

Batch-classifies uncategorized market sources by sending titles to the local
Ollama instance. Runs as a one-time backfill and after each collection cycle.
"""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.database import async_session
from app.models.source import Source

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://192.168.50.114:11434"
OLLAMA_MODEL = "qwen2.5:7b"

VALID_CATEGORIES = [
    "politics", "geopolitics", "economy", "finance", "technology",
    "climate", "health", "sports", "entertainment", "science", "general",
]

SYSTEM_PROMPT = f"""You are a categorizer. Given a prediction market title, respond with ONLY one category from this list:
{', '.join(VALID_CATEGORIES)}

Rules:
- Elections, voting, politicians, government policy → politics
- Wars, international relations, sanctions, military, treaties → geopolitics
- GDP, inflation, interest rates, recession, central banks → economy
- Stocks, crypto, prices, market cap, trading → finance
- AI, software, hardware, quantum computing, tech companies → technology
- Weather, temperature, climate change, emissions → climate
- Disease, vaccines, health policy, medical → health
- Sports matches, scores, tournaments, athletes, FIFA, NBA, esports → sports
- Movies, TV, music, celebrities, awards → entertainment
- Space, physics, biology, research, academic → science
- Anything else → general

Respond with the single category word only. No explanation."""

BATCH_SIZE = 20


async def categorize_sources(limit: int = 0) -> dict:
    """Categorize uncategorized market sources using Ollama.

    Args:
        limit: Max sources to categorize. 0 = all uncategorized.

    Returns:
        Dict with counts per category and total categorized.
    """
    async with async_session() as db:
        query = (
            select(Source)
            .where(Source.signal_type == "market_probability")
            .where(Source.category.is_(None))
            .options(load_only(Source.id, Source.title, Source.category))
        )
        if limit > 0:
            query = query.limit(limit)

        result = await db.execute(query)
        sources = result.scalars().all()

        if not sources:
            return {"categorized": 0, "message": "No uncategorized sources"}

        logger.info(f"Categorizing {len(sources)} sources via Ollama")

        # Build batch prompts — group titles to reduce API calls
        categorized = 0
        category_counts = {}
        failed = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for i in range(0, len(sources), BATCH_SIZE):
                batch = sources[i:i + BATCH_SIZE]
                titles = [s.title for s in batch]

                # Send batch as numbered list for single LLM call
                numbered = "\n".join(f"{j+1}. {t}" for j, t in enumerate(titles))
                prompt = (
                    f"Categorize each prediction market title. "
                    f"Respond with ONLY the number and category, one per line.\n"
                    f"Example: 1. politics\n\n{numbered}"
                )

                try:
                    resp = await client.post(
                        f"{OLLAMA_URL}/api/generate",
                        json={
                            "model": OLLAMA_MODEL,
                            "system": SYSTEM_PROMPT,
                            "prompt": prompt,
                            "stream": False,
                            "options": {"temperature": 0},
                        },
                    )
                    resp.raise_for_status()
                    text = resp.json().get("response", "")

                    # Parse responses
                    categories = _parse_batch_response(text, len(batch))

                    for source, cat in zip(batch, categories):
                        if cat in VALID_CATEGORIES:
                            source.category = cat
                            category_counts[cat] = category_counts.get(cat, 0) + 1
                            categorized += 1
                        else:
                            source.category = "general"
                            category_counts["general"] = category_counts.get("general", 0) + 1
                            categorized += 1

                except Exception as e:
                    logger.warning(f"Ollama batch {i//BATCH_SIZE} failed: {e}")
                    failed += len(batch)

        await db.commit()

    logger.info(f"Categorized {categorized} sources, {failed} failed")
    return {
        "categorized": categorized,
        "failed": failed,
        "categories": category_counts,
    }


def _parse_batch_response(text: str, expected: int) -> list[str]:
    """Parse numbered category responses from LLM output."""
    categories = ["general"] * expected
    for line in text.strip().splitlines():
        line = line.strip().lower()
        if not line:
            continue
        # Handle formats: "1. politics", "1: politics", "1 politics", "1.politics"
        for sep in [". ", ": ", " ", "."]:
            if sep in line:
                parts = line.split(sep, 1)
                try:
                    idx = int(parts[0].strip().rstrip(".")) - 1
                    cat = parts[1].strip().rstrip(".")
                    if 0 <= idx < expected and cat in VALID_CATEGORIES:
                        categories[idx] = cat
                    break
                except (ValueError, IndexError):
                    continue
    return categories
