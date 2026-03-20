import logging
from datetime import date

import httpx

from app.agents.collector.base_indicator import BaseIndicatorCollector, IndicatorRecord

logger = logging.getLogger(__name__)

CBS_API_URL = "https://apis.cbs.gov.il/series/data/list"

CBS_SERIES_MAP = {
    "cpi": {"subject": 120010, "name": "Israel Consumer Price Index", "unit": "index"},
    "housing_price_index": {"subject": 120070, "name": "Israel Housing Price Index", "unit": "index"},
    "unemployment_rate": {"subject": 200010, "name": "Israel Unemployment Rate", "unit": "percent"},
    "construction_starts": {"subject": 220010, "name": "Israel Construction Starts", "unit": "units"},
    "wage_index": {"subject": 120020, "name": "Israel Wage Index", "unit": "index"},
}


class CBSIsraelCollector(BaseIndicatorCollector):
    source_agency = "CBS_IL"

    async def _collect_impl(self, series_ids: list[str]) -> list[IndicatorRecord]:
        records = []
        async with httpx.AsyncClient(timeout=30) as client:
            for series_id in series_ids:
                if series_id not in CBS_SERIES_MAP:
                    logger.warning(f"CBS_IL: unknown series '{series_id}', skipping")
                    continue
                try:
                    records.extend(await self._fetch_series(client, series_id))
                except Exception:
                    logger.exception(f"CBS_IL: failed to fetch {series_id}")

        logger.info(f"CBS_IL: collected {len(records)} observations from {len(series_ids)} series")
        return records

    async def _fetch_series(self, client: httpx.AsyncClient, series_id: str) -> list[IndicatorRecord]:
        info = CBS_SERIES_MAP[series_id]

        response = await client.get(
            CBS_API_URL,
            params={"id": info["subject"], "format": 2, "download": "false", "last": 12},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

        records = []
        data_rows = data if isinstance(data, list) else data.get("DataList", data.get("data", []))
        if isinstance(data_rows, dict):
            data_rows = data_rows.get("Series", [])

        for item in data_rows:
            try:
                period_str = str(item.get("TimePeriod", item.get("period", "")))
                value = item.get("Value", item.get("value"))
                if value is None:
                    continue

                records.append(
                    IndicatorRecord(
                        source_agency="CBS_IL",
                        series_id=series_id,
                        name=info["name"],
                        category="economy",
                        region="IL",
                        value=float(value),
                        unit=info["unit"],
                        period=period_str,
                        release_date=date.today(),
                        extra_data={"cbs_subject": info["subject"]},
                    )
                )
            except (ValueError, TypeError):
                logger.warning(f"CBS_IL: skipping malformed data in {series_id}")

        return records
