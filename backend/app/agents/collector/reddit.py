import asyncio
import hashlib
import json
import logging
import urllib.request
from datetime import datetime, timezone

from app.agents.collector.base import BaseCollector, CollectedItem

logger = logging.getLogger(__name__)

SUBREDDITS = ["worldnews", "technology", "science", "economics"]

SUBREDDIT_CATEGORY_MAP = {
    "worldnews": "geopolitics",
    "technology": "technology",
    "science": "science",
    "economics": "economy",
}

USER_AGENT = "FuturePrediction/1.0"


def _fetch_subreddit(subreddit: str) -> list[dict]:
    """Synchronously fetch hot posts from a subreddit via Reddit JSON API."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=50"

    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning(f"Reddit request failed for r/{subreddit}: {e}")
        return []

    children = data.get("data", {}).get("children", [])
    return [child.get("data", {}) for child in children]


def _search_reddit(query: str, subreddit: str = "all") -> list[dict]:
    """Search Reddit for posts matching a query."""
    import urllib.parse
    url = f"https://www.reddit.com/r/{subreddit}/search.json?{urllib.parse.urlencode({'q': query, 'sort': 'new', 'limit': 15, 'restrict_sr': '1' if subreddit != 'all' else '0'})}"

    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning(f"Reddit search failed for '{query}': {e}")
        return []

    children = data.get("data", {}).get("children", [])
    return [child.get("data", {}) for child in children]


async def _get_interest_keywords() -> list[str]:
    """Pull keywords from user interests."""
    try:
        from sqlalchemy import select
        from app.database import async_session
        from app.models.user_interest import UserInterest

        async with async_session() as db:
            result = await db.execute(select(UserInterest))
            interests = result.scalars().all()
            return [kw for i in interests for kw in (i.keywords or [])]
    except Exception:
        return []


class RedditWorldNewsCollector(BaseCollector):
    platform = "reddit"

    async def collect(self) -> list[CollectedItem]:
        """Collect hot posts from selected subreddits + search for user interests."""
        items: list[CollectedItem] = []
        seen_ids: set[str] = set()

        try:
            for subreddit in SUBREDDITS:
                posts = await asyncio.to_thread(_fetch_subreddit, subreddit)
                logger.debug(
                    f"Reddit: r/{subreddit} returned {len(posts)} posts"
                )

                for post in posts:
                    post_id = post.get("id", "")
                    if not post_id or post_id in seen_ids:
                        continue
                    seen_ids.add(post_id)

                    ext_id = f"{subreddit}_{post_id}"

                    score = post.get("score", 0)
                    num_comments = post.get("num_comments", 0)

                    # Parse created_utc
                    resolution_date = None
                    created_utc = post.get("created_utc")
                    if created_utc:
                        try:
                            resolution_date = (
                                datetime.fromtimestamp(float(created_utc), tz=timezone.utc)
                                .isoformat()
                            )
                        except (ValueError, TypeError, OSError):
                            pass

                    category = SUBREDDIT_CATEGORY_MAP.get(subreddit)

                    items.append(
                        CollectedItem(
                            platform=self.platform,
                            external_id=ext_id,
                            title=post.get("title", ""),
                            description=post.get("selftext", "")[:500] or None,
                            category=category,
                            current_probability=None,
                            resolution_date=resolution_date,
                            signal_type="engagement",
                            raw_data={
                                "subreddit": subreddit,
                                "score": score,
                                "num_comments": num_comments,
                                "url": post.get("url"),
                                "permalink": post.get("permalink"),
                                "author": post.get("author"),
                                "created_utc": created_utc,
                                "upvote_ratio": post.get("upvote_ratio"),
                                "is_self": post.get("is_self"),
                            },
                        )
                    )

            # Also search for user interest keywords
            interest_kws = await _get_interest_keywords()
            for kw in interest_kws:
                search_posts = await asyncio.to_thread(_search_reddit, kw, "all")
                for post in search_posts:
                    post_id = post.get("id", "")
                    if not post_id or post_id in seen_ids:
                        continue
                    seen_ids.add(post_id)

                    sub = post.get("subreddit", "search")
                    ext_id = f"{sub}_{post_id}"
                    score = post.get("score", 0)
                    num_comments = post.get("num_comments", 0)

                    resolution_date = None
                    created_utc = post.get("created_utc")
                    if created_utc:
                        try:
                            resolution_date = (
                                datetime.fromtimestamp(float(created_utc), tz=timezone.utc)
                                .isoformat()
                            )
                        except (ValueError, TypeError, OSError):
                            pass

                    items.append(
                        CollectedItem(
                            platform=self.platform,
                            external_id=ext_id,
                            title=post.get("title", ""),
                            description=post.get("selftext", "")[:500] or None,
                            category=SUBREDDIT_CATEGORY_MAP.get(sub),
                            current_probability=None,
                            resolution_date=resolution_date,
                            signal_type="engagement",
                            raw_data={
                                "subreddit": sub,
                                "score": score,
                                "num_comments": num_comments,
                                "url": post.get("url"),
                                "permalink": post.get("permalink"),
                                "author": post.get("author"),
                                "created_utc": created_utc,
                                "upvote_ratio": post.get("upvote_ratio"),
                                "is_self": post.get("is_self"),
                                "search_keyword": kw,
                            },
                        )
                    )

            logger.info(f"Reddit: collected {len(items)} posts (incl. {len(interest_kws)} interest searches)")

        except Exception as e:
            logger.error(f"Reddit collection failed: {e}")

        return items
