import asyncio
import hashlib
import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime, timezone

from app.agents.collector.base import BaseCollector, CollectedItem

logger = logging.getLogger(__name__)

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

DEFAULT_KEYWORDS = [
    "prediction",
    "forecast",
    "geopolitics",
    "economy",
    "technology",
    "climate",
]


async def _get_interest_keywords() -> list[str]:
    """Pull keywords from user interests in the database."""
    try:
        from sqlalchemy import select
        from app.database import async_session
        from app.models.user_interest import UserInterest

        async with async_session() as db:
            result = await db.execute(select(UserInterest))
            interests = result.scalars().all()
            kws = []
            for interest in interests:
                kws.extend(interest.keywords or [])
            return kws
    except Exception:
        return []

# Map GDELT themes to categories
THEME_CATEGORY_MAP = {
    "ENV_": "climate",
    "ECON_": "economy",
    "POL_": "politics",
    "SOC_": "society",
    "TECH": "technology",
    "MIL_": "military",
    "HEALTH": "health",
    "SCIENCE": "science",
    "TERROR": "security",
    "CYBER": "technology",
    "TAX_": "economy",
    "TRADE": "economy",
    "ELECTION": "politics",
    "CLIMATE": "climate",
    "AI": "technology",
}

REQUEST_DELAY_SECONDS = 2


def _detect_category(article: dict) -> str | None:
    """Detect category from GDELT themes or other article metadata."""
    # Check seendate domain or socialimage for hints
    themes_str = article.get("themes", "") or ""
    if not themes_str:
        # Fall back to domain-based heuristic
        domain = article.get("domain", "")
        if any(t in domain for t in ("tech", "wired", "ars", "verge")):
            return "technology"
        if any(t in domain for t in ("econ", "finance", "bloomberg", "reuters")):
            return "economy"
        return None

    themes_upper = themes_str.upper()
    for prefix, category in THEME_CATEGORY_MAP.items():
        if prefix in themes_upper:
            return category

    return None


def _extract_tone(article: dict) -> float | None:
    """Extract tone (sentiment) score from a GDELT article entry."""
    tone_str = article.get("tone")
    if tone_str is None:
        return None
    try:
        # GDELT tone is a comma-separated string; first value is the overall tone
        return float(str(tone_str).split(",")[0])
    except (ValueError, IndexError):
        return None


def _article_id(article: dict) -> str:
    """Generate a stable external id for a GDELT article."""
    url = article.get("url", "")
    if url:
        return hashlib.sha256(url.encode()).hexdigest()[:16]
    title = article.get("title", "")
    return hashlib.sha256(title.encode()).hexdigest()[:16]


def _fetch_keyword(keyword: str) -> list[dict]:
    """Synchronously fetch articles for a single keyword from GDELT."""
    params = urllib.parse.urlencode({
        "query": keyword,
        "mode": "artlist",
        "maxrecords": "50",
        "format": "json",
    })
    url = f"{GDELT_DOC_API}?{params}"

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "FuturePrediction/1.0")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning(f"GDELT request failed for keyword '{keyword}': {e}")
        return []

    return data.get("articles", [])


class GdeltNewsCollector(BaseCollector):
    platform = "gdelt"

    async def collect(self) -> list[CollectedItem]:
        """Collect news articles from the GDELT DOC API."""
        items: list[CollectedItem] = []
        seen_ids: set[str] = set()

        # Merge default keywords with user interest keywords
        interest_kws = await _get_interest_keywords()
        keywords = list(dict.fromkeys(DEFAULT_KEYWORDS + interest_kws))  # dedupe, preserve order

        try:
            for i, keyword in enumerate(keywords):
                # Rate-limit: wait between requests (skip delay before the first)
                if i > 0:
                    await asyncio.sleep(REQUEST_DELAY_SECONDS)

                articles = await asyncio.to_thread(_fetch_keyword, keyword)
                logger.debug(
                    f"GDELT: keyword '{keyword}' returned {len(articles)} articles"
                )

                for article in articles:
                    ext_id = _article_id(article)
                    if ext_id in seen_ids:
                        continue
                    seen_ids.add(ext_id)

                    tone = _extract_tone(article)
                    category = _detect_category(article)

                    # Parse date
                    resolution_date = None
                    seendate = article.get("seendate")
                    if seendate:
                        try:
                            resolution_date = (
                                datetime.strptime(seendate, "%Y%m%dT%H%M%SZ")
                                .replace(tzinfo=timezone.utc)
                                .isoformat()
                            )
                        except ValueError:
                            pass

                    items.append(
                        CollectedItem(
                            platform=self.platform,
                            external_id=ext_id,
                            title=article.get("title", ""),
                            description=article.get("url"),
                            category=category,
                            current_probability=None,
                            resolution_date=resolution_date,
                            signal_type="news",
                            raw_data={
                                "url": article.get("url"),
                                "domain": article.get("domain"),
                                "language": article.get("language"),
                                "seendate": article.get("seendate"),
                                "socialimage": article.get("socialimage"),
                                "tone": tone,
                                "keyword": keyword,
                            },
                        )
                    )

            logger.info(f"GDELT: collected {len(items)} articles")

        except Exception as e:
            logger.error(f"GDELT collection failed: {e}")

        return items
