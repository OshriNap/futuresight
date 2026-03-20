import logging

import httpx

from app.agents.collector.base import BaseCollector, CollectedItem

logger = logging.getLogger(__name__)

MANIFOLD_API = "https://api.manifold.markets/v0"


class ManifoldCollector(BaseCollector):
    platform = "manifold"

    @staticmethod
    async def _get_interest_terms() -> list[str]:
        """Return combined keywords + market_filters from enabled UserInterests."""
        try:
            from sqlalchemy import select
            from app.database import async_session
            from app.models.user_interest import UserInterest

            async with async_session() as db:
                result = await db.execute(
                    select(UserInterest).where(UserInterest.enabled.is_(True))
                )
                interests = result.scalars().all()
                terms = []
                for i in interests:
                    terms.extend(i.keywords or [])
                    terms.extend(i.market_filters or [])
                # Deduplicate while preserving order
                return list(dict.fromkeys(terms))
        except Exception:
            return []

    async def collect(self) -> list[CollectedItem]:
        """Collect prediction markets from Manifold Markets API, driven by user interests."""
        items = []
        seen_ids: set[str] = set()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Search terms driven entirely by user interests
                search_terms = await self._get_interest_terms()

                for term in search_terms:
                    try:
                        response = await client.get(
                            f"{MANIFOLD_API}/search-markets",
                            params={
                                "term": term,
                                "limit": 30,
                                "filter": "open",
                                "sort": "liquidity",
                            },
                        )
                        response.raise_for_status()
                        markets = response.json()
                    except httpx.HTTPError as e:
                        logger.warning(f"Manifold search failed for '{term}': {e}")
                        continue

                    for market in markets:
                        mid = market.get("id", "")
                        if not mid or mid in seen_ids:
                            continue
                        seen_ids.add(mid)

                        # Only binary markets have a single probability
                        if market.get("outcomeType") != "BINARY":
                            continue

                        probability = market.get("probability")
                        if probability is None:
                            continue

                        # Parse close time (epoch ms)
                        close_time = market.get("closeTime")
                        resolution_date = None
                        if close_time:
                            from datetime import datetime, timezone
                            try:
                                resolution_date = datetime.fromtimestamp(
                                    close_time / 1000, tz=timezone.utc
                                ).isoformat()
                            except (ValueError, TypeError, OSError):
                                pass

                        items.append(
                            CollectedItem(
                                platform=self.platform,
                                external_id=mid,
                                title=market.get("question", ""),
                                description=market.get("textDescription", market.get("description", ""))[:500] if market.get("textDescription") or market.get("description") else None,
                                category=_guess_category(market.get("question", "")),
                                current_probability=probability,
                                resolution_date=resolution_date,
                                signal_type="market_probability",
                                raw_data={
                                    "slug": market.get("slug"),
                                    "url": market.get("url"),
                                    "volume": market.get("volume", 0),
                                    "totalLiquidity": market.get("totalLiquidity", 0),
                                    "uniqueBettorCount": market.get("uniqueBettorCount", 0),
                                    "isResolved": market.get("isResolved", False),
                                    "creatorUsername": market.get("creatorUsername"),
                                    "mechanism": market.get("mechanism"),
                                    "lastUpdatedTime": market.get("lastUpdatedTime"),
                                },
                            )
                        )

            logger.info(f"Manifold: collected {len(items)} markets")

        except Exception as e:
            logger.error(f"Manifold collection failed: {e}")

        return items


def _guess_category(title: str) -> str:
    lower = title.lower()
    if any(w in lower for w in ["bitcoin", "ethereum", "crypto", "stock", "price", "market cap"]):
        return "finance"
    if any(w in lower for w in ["election", "president", "senate", "governor", "democrat", "republican", "vote"]):
        return "politics"
    if any(w in lower for w in ["war", "invasion", "sanction", "military", "nato", "nuclear"]):
        return "geopolitics"
    if any(w in lower for w in ["ai", "quantum", "openai", "google", "apple", "tech", "software"]):
        return "technology"
    if any(w in lower for w in ["climate", "temperature", "weather"]):
        return "climate"
    if any(w in lower for w in ["covid", "vaccine", "health", "disease"]):
        return "health"
    if any(w in lower for w in ["gdp", "inflation", "fed", "interest rate", "recession"]):
        return "economy"
    return "general"
