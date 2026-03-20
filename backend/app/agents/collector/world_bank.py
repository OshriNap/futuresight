import logging
from datetime import date

import httpx

from app.agents.collector.base_indicator import BaseIndicatorCollector, IndicatorRecord

logger = logging.getLogger(__name__)

WB_API_URL = "https://api.worldbank.org/v2"

WB_SERIES_MAP = {
    "NY.GDP.MKTP.CD": {"name": "GDP (current US$)", "unit": "usd"},
    "NY.GDP.PCAP.CD": {"name": "GDP per capita (current US$)", "unit": "usd"},
    "SL.UEM.TOTL.ZS": {"name": "Unemployment (% of labor force)", "unit": "percent"},
    "FP.CPI.TOTL.ZG": {"name": "Inflation, consumer prices (annual %)", "unit": "percent"},
    "EG.USE.PCAP.KG.OE": {"name": "Energy use (kg oil equivalent per capita)", "unit": "kg_oe"},
}


class WorldBankCollector(BaseIndicatorCollector):
    source_agency = "WORLD_BANK"

    async def _collect_impl(self, series_ids: list[str]) -> list[IndicatorRecord]:
        records = []
        async with httpx.AsyncClient(timeout=30) as client:
            for series_spec in series_ids:
                try:
                    if ":" in series_spec:
                        country, indicator = series_spec.split(":", 1)
                    else:
                        country, indicator = "WLD", series_spec

                    records.extend(await self._fetch_series(client, country, indicator))
                except Exception:
                    logger.exception(f"WORLD_BANK: failed to fetch {series_spec}")

        logger.info(f"WORLD_BANK: collected {len(records)} observations from {len(series_ids)} series")
        return records

    async def _fetch_series(self, client: httpx.AsyncClient, country: str, indicator: str) -> list[IndicatorRecord]:
        response = await client.get(
            f"{WB_API_URL}/country/{country}/indicator/{indicator}",
            params={"format": "json", "per_page": 10, "mrv": 10},
        )
        response.raise_for_status()
        data = response.json()

        # World Bank returns [metadata, data_array]
        if not isinstance(data, list) or len(data) < 2:
            return []

        records = []
        info = WB_SERIES_MAP.get(indicator, {"name": indicator, "unit": "unknown"})
        region = country if len(country) == 2 else "global"

        for item in data[1] or []:
            if item.get("value") is None:
                continue
            try:
                records.append(
                    IndicatorRecord(
                        source_agency="WORLD_BANK",
                        series_id=f"{country}:{indicator}" if country != "WLD" else indicator,
                        name=f"{info['name']} — {item.get('country', {}).get('value', country)}",
                        category="economy",
                        region=region,
                        value=float(item["value"]),
                        unit=info["unit"],
                        period=item.get("date", ""),
                        release_date=date.today(),
                        extra_data={"country_code": country, "wb_indicator": indicator},
                    )
                )
            except (ValueError, TypeError):
                logger.warning(f"WORLD_BANK: skipping malformed data for {indicator}")

        return records
