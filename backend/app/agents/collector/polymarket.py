import logging

import httpx

from app.agents.collector.base import BaseCollector, CollectedItem

logger = logging.getLogger(__name__)

GAMMA_API_URL = "https://gamma-api.polymarket.com"


class PolymarketCollector(BaseCollector):
    platform = "polymarket"

    async def collect(self) -> list[CollectedItem]:
        """Collect active markets from Polymarket's Gamma API."""
        items = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Fetch active markets
                response = await client.get(
                    f"{GAMMA_API_URL}/markets",
                    params={
                        "active": "true",
                        "closed": "false",
                        "limit": 100,
                        "order": "volume",
                        "ascending": "false",
                    },
                )
                response.raise_for_status()
                markets = response.json()

                for market in markets:
                    # Extract the best probability from outcomes
                    outcomes = market.get("outcomes", [])
                    prices = market.get("outcomePrices", [])

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
                        )
                    )

            # Save to database
            saved = await self.save_items(items)
            logger.info(f"Polymarket: collected {len(items)} markets, {saved} new")

        except httpx.HTTPError as e:
            logger.error(f"Polymarket collection failed: {e}")

        return items
