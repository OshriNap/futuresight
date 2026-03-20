import logging

from sqlalchemy import select

from app.agents.collector.cbs_israel import CBSIsraelCollector
from app.agents.collector.fred import FREDCollector
from app.agents.collector.world_bank import WorldBankCollector
from app.database import async_session
from app.models.user_interest import UserInterest

logger = logging.getLogger(__name__)

COLLECTORS = {
    "FRED": FREDCollector,
    "CBS_IL": CBSIsraelCollector,
    "WORLD_BANK": WorldBankCollector,
}


async def _get_series_by_agency() -> dict[str, list[str]]:
    """Parse UserInterest indicators into per-agency series lists."""
    agency_series: dict[str, list[str]] = {}

    async with async_session() as session:
        result = await session.execute(
            select(UserInterest).where(UserInterest.enabled.is_(True))
        )
        interests = result.scalars().all()

    for interest in interests:
        for indicator_spec in interest.indicators or []:
            if ":" not in indicator_spec:
                continue
            agency, series_id = indicator_spec.split(":", 1)
            agency_series.setdefault(agency, []).append(series_id)

    return agency_series


async def collect_indicators() -> dict:
    """Collect indicators from all government sources based on UserInterest config."""
    agency_series = await _get_series_by_agency()
    results = {}

    for agency, series_ids in agency_series.items():
        if agency not in COLLECTORS:
            logger.warning(f"Unknown indicator agency: {agency}")
            continue

        collector = COLLECTORS[agency]()
        try:
            records = await collector.collect(series_ids)
            saved = await collector.save_indicators(records)
            results[agency] = {"collected": len(records), "saved": saved}
        except Exception:
            logger.exception(f"Failed to collect from {agency}")
            results[agency] = {"error": True}

    logger.info(f"Indicator collection complete: {results}")
    return results
