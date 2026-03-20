import logging
import os
from datetime import date, datetime

import httpx

from app.agents.collector.base_indicator import BaseIndicatorCollector, IndicatorRecord

logger = logging.getLogger(__name__)

FRED_API_URL = "https://api.stlouisfed.org/fred"

SERIES_NAMES = {
    "UNRATE": "US Unemployment Rate",
    "CPIAUCSL": "US Consumer Price Index",
    "GDP": "US Gross Domestic Product",
    "FEDFUNDS": "Federal Funds Effective Rate",
    "UMCSENT": "US Consumer Sentiment",
    "HOUST": "US Housing Starts",
    "DGS10": "10-Year Treasury Yield",
    "VIXCLS": "CBOE Volatility Index (VIX)",
    "DCOILWTICO": "Crude Oil Price (WTI)",
    "IRLTLT01ILM156N": "Israel Long-Term Interest Rate",
}

SERIES_UNITS = {
    "UNRATE": "percent",
    "CPIAUCSL": "index",
    "GDP": "billions_usd",
    "FEDFUNDS": "percent",
    "UMCSENT": "index",
    "HOUST": "thousands",
    "DGS10": "percent",
    "VIXCLS": "index",
    "DCOILWTICO": "usd",
    "IRLTLT01ILM156N": "percent",
}


class FREDCollector(BaseIndicatorCollector):
    source_agency = "FRED"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")
        if not self.api_key:
            logger.warning("FRED_API_KEY not set — FRED collection will be skipped")

    async def _collect_impl(self, series_ids: list[str]) -> list[IndicatorRecord]:
        if not self.api_key:
            logger.warning("Skipping FRED collection: no API key")
            return []

        records = []
        async with httpx.AsyncClient(timeout=30) as client:
            for series_id in series_ids:
                try:
                    records.extend(await self._fetch_series(client, series_id))
                except Exception:
                    logger.exception(f"FRED: failed to fetch {series_id}")

        logger.info(f"FRED: collected {len(records)} observations from {len(series_ids)} series")
        return records

    async def _fetch_series(self, client: httpx.AsyncClient, series_id: str) -> list[IndicatorRecord]:
        response = await client.get(
            f"{FRED_API_URL}/series/observations",
            params={
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 12,
            },
        )
        response.raise_for_status()
        data = response.json()

        records = []
        for obs in data.get("observations", []):
            if obs.get("value") == ".":
                continue
            try:
                obs_date = datetime.strptime(obs["date"], "%Y-%m-%d").date()
                records.append(
                    IndicatorRecord(
                        source_agency="FRED",
                        series_id=series_id,
                        name=SERIES_NAMES.get(series_id, series_id),
                        category="economy",
                        region=self._guess_region(series_id),
                        value=float(obs["value"]),
                        unit=SERIES_UNITS.get(series_id, "unknown"),
                        period=obs["date"][:7],
                        release_date=obs_date,
                        extra_data={"realtime_start": obs.get("realtime_start")},
                    )
                )
            except (ValueError, KeyError):
                logger.warning(f"FRED: skipping malformed observation in {series_id}")

        return records

    @staticmethod
    def _guess_region(series_id: str) -> str:
        if "ILM" in series_id or "ISR" in series_id:
            return "IL"
        return "US"
