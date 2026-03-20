import logging

import httpx

from app.agents.collector.base import BaseCollector, CollectedItem

logger = logging.getLogger(__name__)

GAMMA_API_URL = "https://gamma-api.polymarket.com"


class PolymarketCollector(BaseCollector):
    platform = "polymarket"

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
        """Collect active markets from Polymarket's Gamma API, driven by user interests."""
        items = []
        seen_ids: set[str] = set()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                markets = []

                # Search only for user interest terms (keywords + market_filters)
                interest_terms = await self._get_interest_terms()
                for term in interest_terms:
                    try:
                        r = await client.get(
                            f"{GAMMA_API_URL}/markets",
                            params={
                                "active": "true",
                                "closed": "false",
                                "limit": 20,
                                "tag": term,
                            },
                        )
                        r.raise_for_status()
                        markets.extend(r.json())
                    except Exception:
                        pass

                for market in markets:
                    mid = str(market.get("id", ""))
                    if mid in seen_ids:
                        continue
                    seen_ids.add(mid)
                    # Extract the best probability from outcomes
                    prices = market.get("outcomePrices", [])

                    # outcomePrices can be a JSON string like '["0.355", "0.645"]'
                    if isinstance(prices, str):
                        import json
                        try:
                            prices = json.loads(prices)
                        except (json.JSONDecodeError, TypeError):
                            prices = []

                    probability = None
                    if prices and len(prices) > 0:
                        try:
                            probability = float(prices[0])
                        except (ValueError, TypeError):
                            pass

                    items.append(
                        CollectedItem(
                            platform=self.platform,
                            external_id=str(market.get("id", "")),
                            title=market.get("question", market.get("title", "")),
                            description=market.get("description"),
                            category=market.get("groupSlug"),
                            current_probability=probability,
                            resolution_date=market.get("endDate"),
                            raw_data=market,
                            signal_type="market_probability",
                        )
                    )

            logger.info(f"Polymarket: collected {len(items)} markets")

        except httpx.HTTPError as e:
            logger.error(f"Polymarket collection failed: {e}")

        return items
