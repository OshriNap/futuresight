"""Seed default UserInterest records. Run once or idempotently."""
import asyncio
import logging

from sqlalchemy import select

from app.database import async_session, create_tables
from app.models.user_interest import UserInterest

logger = logging.getLogger(__name__)

DEFAULT_INTERESTS = [
    {
        "name": "Israeli Economy",
        "keywords": ["Israel economy", "Israeli inflation", "Bank of Israel", "shekel", "Israeli housing"],
        "category": "economy",
        "priority": "high",
        "region": "IL",
        "indicators": [
            "FRED:IRLTLT01ILM156N",
            "CBS_IL:cpi",
            "CBS_IL:housing_price_index",
            "CBS_IL:unemployment_rate",
            "CBS_IL:construction_starts",
        ],
        "market_filters": ["israel", "bank-of-israel", "shekel", "tel-aviv"],
    },
    {
        "name": "US Economy",
        "keywords": ["US economy", "Federal Reserve", "US inflation", "US unemployment", "US GDP"],
        "category": "economy",
        "priority": "high",
        "region": "US",
        "indicators": ["FRED:UNRATE", "FRED:CPIAUCSL", "FRED:GDP", "FRED:FEDFUNDS", "FRED:UMCSENT", "FRED:HOUST"],
        "market_filters": ["federal-reserve", "us-economy", "us-recession", "inflation"],
    },
    {
        "name": "Geopolitics — Middle East",
        "keywords": ["Middle East", "Iran", "Saudi Arabia", "Gaza", "Lebanon", "Syria"],
        "category": "geopolitics",
        "priority": "high",
        "region": "global",
        "indicators": [],
        "market_filters": ["iran", "middle-east", "gaza", "israel-war"],
    },
    {
        "name": "Geopolitics — US-China",
        "keywords": ["US China", "Taiwan", "trade war", "sanctions China", "South China Sea"],
        "category": "geopolitics",
        "priority": "medium",
        "region": "global",
        "indicators": [],
        "market_filters": ["china", "taiwan", "us-china"],
    },
    {
        "name": "AI & Technology",
        "keywords": ["artificial intelligence", "AGI", "LLM", "machine learning", "quantum computing", "semiconductor"],
        "category": "technology",
        "priority": "high",
        "region": "global",
        "indicators": [],
        "market_filters": ["ai", "openai", "google-ai", "artificial-intelligence"],
    },
    {
        "name": "Climate & Energy",
        "keywords": ["climate change", "renewable energy", "carbon emissions", "solar", "EV", "oil price"],
        "category": "climate",
        "priority": "medium",
        "region": "global",
        "indicators": ["FRED:DCOILWTICO"],
        "market_filters": ["climate", "energy-transition", "oil-price"],
    },
    {
        "name": "Global Financial Markets",
        "keywords": ["stock market", "S&P 500", "treasury yields", "VIX", "bond market", "commodities"],
        "category": "finance",
        "priority": "medium",
        "region": "global",
        "indicators": ["FRED:DGS10", "FRED:VIXCLS", "FRED:DCOILWTICO"],
        "market_filters": ["sp500", "stock-market", "treasury", "recession"],
    },
]


async def seed_interests():
    await create_tables()

    async with async_session() as session:
        existing = await session.execute(select(UserInterest))
        existing_names = {i.name for i in existing.scalars().all()}

        added = 0
        for interest_data in DEFAULT_INTERESTS:
            if interest_data["name"] in existing_names:
                logger.info(f"Skipping existing interest: {interest_data['name']}")
                continue

            interest = UserInterest(**interest_data, enabled=True)
            session.add(interest)
            added += 1

        await session.commit()
        logger.info(f"Seeded {added} new interests (skipped {len(DEFAULT_INTERESTS) - added})")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_interests())
