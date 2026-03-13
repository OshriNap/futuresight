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


class RedditWorldNewsCollector(BaseCollector):
    platform = "reddit"

    async def collect(self) -> list[CollectedItem]:
        """Collect hot posts from selected subreddits."""
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

                    # Use score to derive a rough "probability" (engagement signal)
                    # Normalise: cap at 50k upvotes -> map to [0, 1]
                    probability = round(min(score / 50000, 1.0), 4) if score > 0 else 0.0

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
                            current_probability=probability,
                            resolution_date=resolution_date,
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

            # Persist
            saved = await self.save_items(items)
            logger.info(f"Reddit: collected {len(items)} posts, {saved} new")

        except Exception as e:
            logger.error(f"Reddit collection failed: {e}")

        return items
