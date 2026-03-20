# Indicator-Driven Intelligence Platform — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the prediction platform from a firehose of trivial prediction market bets into an interest-driven intelligence system grounded in government statistical data, with layered insights (data → trend → prediction → action items).

**Architecture:** Two parallel tracks — (1) curated prediction markets filtered by UserInterest, and (2) government indicator time-series from FRED, CBS Israel, and World Bank. Both feed into Claude Code scheduled tasks that generate layered Insight records. UserInterest becomes the control plane driving all collection.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, httpx, Next.js 14, TypeScript, Tailwind, recharts

**Spec:** `docs/superpowers/specs/2026-03-20-indicator-intelligence-platform-design.md`

---

## Pre-flight: Commit all existing changes

Before any implementation, commit all current uncommitted work so we have a clean baseline.

- [ ] **Step 1: Stage and commit all current changes**

```bash
cd /home/oshrin/projects/future_prediction
git add -A
git commit -m "WIP: save current state before indicator intelligence platform work"
```

---

## Task 1: Indicator Model

**Files:**
- Create: `backend/app/models/indicator.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create the Indicator model**

Create `backend/app/models/indicator.py`:

```python
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Indicator(Base):
    __tablename__ = "indicators"
    __table_args__ = (
        UniqueConstraint("source_agency", "series_id", "period", name="uq_indicator_series_period"),
        Index("ix_indicator_series_release", "series_id", "release_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    source_agency: Mapped[str] = mapped_column(String(50), index=True)
    series_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(10), nullable=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    period: Mapped[str] = mapped_column(String(20))
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 2: Register Indicator in models `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.indicator import Indicator
```

And add `Indicator` to the `__all__` list.

- [ ] **Step 3: Verify table creation**

```bash
cd /home/oshrin/projects/future_prediction/backend
python -c "import asyncio; from app.database import create_tables; asyncio.run(create_tables()); print('OK')"
```

Expected: `OK` (tables auto-created on startup, no Alembic needed).

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/indicator.py backend/app/models/__init__.py
git commit -m "feat: add Indicator model for government time-series data"
```

---

## Task 2: Insight Model

**Files:**
- Create: `backend/app/models/insight.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create the Insight model**

Create `backend/app/models/insight.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    domain: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(500))
    ground_truth: Mapped[str] = mapped_column(Text)
    trend_analysis: Mapped[str] = mapped_column(Text)
    prediction: Mapped[str] = mapped_column(Text)
    action_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[str] = mapped_column(String(20), default="medium")
    sources: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)
```

The `sources` field uses structured format: `{"indicators": [...], "market_sources": [...], "news_sources": [...]}`.

- [ ] **Step 2: Register Insight in models `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.insight import Insight
```

And add `Insight` to the `__all__` list.

- [ ] **Step 3: Verify table creation**

```bash
cd /home/oshrin/projects/future_prediction/backend
python -c "import asyncio; from app.database import create_tables; asyncio.run(create_tables()); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/insight.py backend/app/models/__init__.py
git commit -m "feat: add Insight model for layered LLM analysis"
```

---

## Task 3: Extend UserInterest Model

**Files:**
- Modify: `backend/app/models/user_interest.py`
- Modify: `backend/app/api/interests.py`

- [ ] **Step 1: Add new fields to UserInterest model**

Add these fields to the `UserInterest` class in `backend/app/models/user_interest.py`:

```python
    indicators: Mapped[list | None] = mapped_column(JSON, nullable=True)
    market_filters: Mapped[list | None] = mapped_column(JSON, nullable=True)
    region: Mapped[str | None] = mapped_column(String(10), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 2: Update Pydantic schemas in interests.py**

In `backend/app/api/interests.py`, update `InterestCreate`:

```python
class InterestCreate(BaseModel):
    name: str
    description: str | None = None
    keywords: list[str]
    category: str | None = None
    priority: str = "medium"
    notification_enabled: bool = True
    indicators: list[str] | None = None
    market_filters: list[str] | None = None
    region: str | None = None
    enabled: bool = True
```

Update `InterestResponse`:

```python
class InterestResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    keywords: list[str]
    category: str | None
    priority: str
    notification_enabled: bool
    indicators: list[str] | None
    market_filters: list[str] | None
    region: str | None
    enabled: bool
    created_at: datetime
    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Verify by starting the API briefly**

```bash
cd /home/oshrin/projects/future_prediction/backend
timeout 5 python -m uvicorn app.main:app --host 0.0.0.0 --port 8099 2>&1 || true
```

Expected: starts without import errors (will timeout after 5s, that's fine).

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/user_interest.py backend/app/api/interests.py
git commit -m "feat: extend UserInterest with indicators, market_filters, region, enabled"
```

---

## Task 4: BaseIndicatorCollector

**Files:**
- Create: `backend/app/agents/collector/base_indicator.py`

- [ ] **Step 1: Create BaseIndicatorCollector**

Create `backend/app/agents/collector/base_indicator.py`:

```python
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.database import async_session
from app.models.indicator import Indicator

logger = logging.getLogger(__name__)


@dataclass
class IndicatorRecord:
    source_agency: str
    series_id: str
    name: str
    category: str | None
    region: str | None
    value: float
    unit: str | None
    period: str
    release_date: date | None = None
    metadata: dict | None = None


class BaseIndicatorCollector(ABC):
    source_agency: str  # Must be set by subclass

    @abstractmethod
    async def _collect_impl(self, series_ids: list[str]) -> list[IndicatorRecord]:
        """Collect indicator data for the given series IDs. Subclasses implement this."""

    async def collect(self, series_ids: list[str]) -> list[IndicatorRecord]:
        """Collect with retry logic (3 attempts, exponential backoff)."""
        for attempt in range(3):
            try:
                return await self._collect_impl(series_ids)
            except Exception:
                if attempt == 2:
                    raise
                wait = 2 ** attempt
                logger.warning(f"{self.source_agency}: attempt {attempt + 1} failed, retrying in {wait}s")
                await asyncio.sleep(wait)
        return []  # unreachable, but satisfies type checker

    async def save_indicators(self, records: list[IndicatorRecord]) -> int:
        """Upsert indicator records. Returns count of new/updated records."""
        if not records:
            return 0

        saved = 0
        async with async_session() as session:
            for record in records:
                existing = await session.execute(
                    select(Indicator).where(
                        Indicator.source_agency == record.source_agency,
                        Indicator.series_id == record.series_id,
                        Indicator.period == record.period,
                    )
                )
                indicator = existing.scalar_one_or_none()

                if indicator:
                    if indicator.value != record.value:
                        indicator.value = record.value
                        indicator.release_date = record.release_date
                        indicator.metadata = record.metadata
                        flag_modified(indicator, "metadata")
                        saved += 1
                else:
                    indicator = Indicator(
                        source_agency=record.source_agency,
                        series_id=record.series_id,
                        name=record.name,
                        category=record.category,
                        region=record.region,
                        value=record.value,
                        unit=record.unit,
                        period=record.period,
                        release_date=record.release_date,
                        metadata=record.metadata,
                    )
                    session.add(indicator)
                    saved += 1

            await session.commit()

        logger.info(f"{self.source_agency}: saved {saved}/{len(records)} indicators")
        return saved
```

Note: Subclasses implement `_collect_impl()` instead of `collect()`. The base `collect()` wraps it with retry logic.

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/collector/base_indicator.py
git commit -m "feat: add BaseIndicatorCollector for government data sources"
```

---

## Task 5: FRED Collector

**Files:**
- Create: `backend/app/agents/collector/fred.py`

- [ ] **Step 1: Create FRED collector**

Create `backend/app/agents/collector/fred.py`:

```python
import logging
import os
from datetime import date, datetime

import httpx

from app.agents.collector.base_indicator import BaseIndicatorCollector, IndicatorRecord

logger = logging.getLogger(__name__)

FRED_API_URL = "https://api.stlouisfed.org/fred"

# Human-readable names for common series
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
                        metadata={"realtime_start": obs.get("realtime_start")},
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/collector/fred.py
git commit -m "feat: add FRED collector for US economic indicators"
```

---

## Task 6: CBS Israel Collector

**Files:**
- Create: `backend/app/agents/collector/cbs_israel.py`

- [ ] **Step 1: Create CBS Israel collector**

Create `backend/app/agents/collector/cbs_israel.py`:

```python
import logging
from datetime import date

import httpx

from app.agents.collector.base_indicator import BaseIndicatorCollector, IndicatorRecord

logger = logging.getLogger(__name__)

CBS_API_URL = "https://apis.cbs.gov.il/series/data/list"

# Map our friendly series IDs to CBS internal subject/series codes
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

    async def _fetch_series(
        self, client: httpx.AsyncClient, series_id: str
    ) -> list[IndicatorRecord]:
        info = CBS_SERIES_MAP[series_id]

        response = await client.get(
            CBS_API_URL,
            params={"id": info["subject"], "format": 2, "download": "false", "last": 12},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

        records = []
        # CBS API returns nested data structure — adapt to actual response format
        # The format varies by endpoint; we handle the common tabular format
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
                        metadata={"cbs_subject": info["subject"]},
                    )
                )
            except (ValueError, TypeError):
                logger.warning(f"CBS_IL: skipping malformed data in {series_id}")

        return records
```

Note: CBS API response format may need adjustment during integration testing. The collector is structured to handle variations — the parsing logic in `_fetch_series` will likely need tuning once we can test against the real API.

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/collector/cbs_israel.py
git commit -m "feat: add CBS Israel collector for Israeli economic indicators"
```

---

## Task 7: World Bank Collector

**Files:**
- Create: `backend/app/agents/collector/world_bank.py`

- [ ] **Step 1: Create World Bank collector**

Create `backend/app/agents/collector/world_bank.py`:

```python
import logging
from datetime import date

import httpx

from app.agents.collector.base_indicator import BaseIndicatorCollector, IndicatorRecord

logger = logging.getLogger(__name__)

WB_API_URL = "https://api.worldbank.org/v2"

# Map series IDs to World Bank indicator codes + metadata
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
        # Parse series_ids which may include country code: "IL:NY.GDP.MKTP.CD"
        # or plain indicator code (defaults to "WLD" for world)
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

    async def _fetch_series(
        self, client: httpx.AsyncClient, country: str, indicator: str
    ) -> list[IndicatorRecord]:
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
                        metadata={"country_code": country, "wb_indicator": indicator},
                    )
                )
            except (ValueError, TypeError):
                logger.warning(f"WORLD_BANK: skipping malformed data for {indicator}")

        return records
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/collector/world_bank.py
git commit -m "feat: add World Bank collector for global economic indicators"
```

---

## Task 8: Indicator Collection Task

**Files:**
- Create: `backend/app/tasks/indicator_tasks.py`

- [ ] **Step 1: Create the indicator collection orchestrator**

Create `backend/app/tasks/indicator_tasks.py`:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/tasks/indicator_tasks.py
git commit -m "feat: add indicator collection task orchestrator"
```

---

## Task 9: Indicators API

**Files:**
- Create: `backend/app/api/indicators.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create indicators router**

Create `backend/app/api/indicators.py`:

```python
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.indicator import Indicator

router = APIRouter()


class IndicatorResponse(BaseModel):
    id: uuid.UUID
    source_agency: str
    series_id: str
    name: str
    category: str | None
    region: str | None
    value: float
    unit: str | None
    period: str
    release_date: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[IndicatorResponse])
async def list_indicators(
    agency: str | None = Query(None),
    category: str | None = Query(None),
    region: str | None = Query(None),
    series_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(Indicator).order_by(Indicator.release_date.desc())

    if agency:
        query = query.where(Indicator.source_agency == agency)
    if category:
        query = query.where(Indicator.category == category)
    if region:
        query = query.where(Indicator.region == region)
    if series_id:
        query = query.where(Indicator.series_id == series_id)

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/history/{series_id}")
async def indicator_history(
    series_id: str,
    agency: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Indicator)
        .where(Indicator.series_id == series_id)
        .order_by(Indicator.period.asc())
    )
    if agency:
        query = query.where(Indicator.source_agency == agency)

    result = await db.execute(query)
    rows = result.scalars().all()

    return {
        "series_id": series_id,
        "agency": rows[0].source_agency if rows else agency,
        "name": rows[0].name if rows else series_id,
        "unit": rows[0].unit if rows else None,
        "data": [
            {"period": r.period, "value": r.value, "release_date": str(r.release_date) if r.release_date else None}
            for r in rows
        ],
    }
```

- [ ] **Step 2: Register the router in main.py**

Add to `backend/app/main.py` imports:

```python
from app.api import indicators
```

Add router registration (after existing routers):

```python
app.include_router(indicators.router, prefix="/api/indicators", tags=["indicators"])
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/indicators.py backend/app/main.py
git commit -m "feat: add indicators API with list and history endpoints"
```

---

## Task 10: Insights API

**Files:**
- Create: `backend/app/api/insights.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create insights router**

Create `backend/app/api/insights.py`:

```python
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.insight import Insight

router = APIRouter()


class InsightCreate(BaseModel):
    domain: str
    title: str
    ground_truth: str
    trend_analysis: str
    prediction: str
    action_items: list[str] | None = None
    confidence: str = "medium"
    sources: dict | None = None


class InsightResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    domain: str
    title: str
    ground_truth: str
    trend_analysis: str
    prediction: str
    action_items: list[str] | None
    confidence: str
    sources: dict | None
    stale: bool

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[InsightResponse])
async def list_insights(
    domain: str | None = Query(None),
    include_stale: bool = Query(False),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Insight).order_by(Insight.created_at.desc())

    if domain:
        query = query.where(Insight.domain == domain)
    if not include_stale:
        query = query.where(Insight.stale.is_(False))

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{insight_id}", response_model=InsightResponse)
async def get_insight(insight_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Insight).where(Insight.id == insight_id))
    insight = result.scalar_one_or_none()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    return insight


@router.post("/", response_model=InsightResponse)
async def create_insight(body: InsightCreate, db: AsyncSession = Depends(get_db)):
    # Mark previous insights for this domain as stale
    await db.execute(
        update(Insight)
        .where(Insight.domain == body.domain, Insight.stale.is_(False))
        .values(stale=True)
    )

    insight = Insight(
        domain=body.domain,
        title=body.title,
        ground_truth=body.ground_truth,
        trend_analysis=body.trend_analysis,
        prediction=body.prediction,
        action_items=body.action_items,
        confidence=body.confidence,
        sources=body.sources,
    )
    db.add(insight)
    await db.commit()
    await db.refresh(insight)
    return insight
```

- [ ] **Step 2: Register the router in main.py**

Add to `backend/app/main.py` imports:

```python
from app.api import insights
```

Add router registration:

```python
app.include_router(insights.router, prefix="/api/insights", tags=["insights"])
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/insights.py backend/app/main.py
git commit -m "feat: add insights API with CRUD and auto-stale on domain update"
```

---

## Task 11: Insight Context & Generation Meta Endpoints

**Files:**
- Modify: `backend/app/api/meta.py`

- [ ] **Step 1: Add insight-context endpoint to meta.py**

Add these imports at the top of `backend/app/api/meta.py` (only add ones not already present — `HTTPException`, `Depends`, `get_db`, `Source` are likely already imported):

```python
import uuid as uuid_mod

from app.models.indicator import Indicator
from app.models.insight import Insight
from app.tasks.indicator_tasks import collect_indicators
```

Add these endpoints:

```python
@router.get("/insight-context/{interest_id}")
async def get_insight_context(interest_id: str, db: AsyncSession = Depends(get_db)):
    """Gather all data for an interest domain — used by Claude Code to generate insights."""
    from app.models.user_interest import UserInterest
    from app.models.source import Source

    interest = await db.get(UserInterest, uuid_mod.UUID(interest_id))
    if not interest:
        raise HTTPException(status_code=404, detail="Interest not found")

    # Recent indicators for this interest's series
    indicator_ids = []
    for spec in interest.indicators or []:
        if ":" in spec:
            _, series_id = spec.split(":", 1)
            indicator_ids.append(series_id)

    indicators_q = await db.execute(
        select(Indicator)
        .where(Indicator.series_id.in_(indicator_ids) if indicator_ids else Indicator.id.is_(None))
        .order_by(Indicator.release_date.desc())
        .limit(50)
    )
    indicators = indicators_q.scalars().all()

    # Recent market sources matching this interest
    keywords = interest.keywords or []
    market_filters = interest.market_filters or []
    search_terms = keywords + market_filters

    market_sources = []
    if search_terms:
        all_sources_q = await db.execute(
            select(Source)
            .where(Source.signal_type == "market_probability")
            .order_by(Source.updated_at.desc())
            .limit(500)
        )
        all_sources = all_sources_q.scalars().all()
        for s in all_sources:
            title_lower = (s.title or "").lower()
            if any(term.lower() in title_lower for term in search_terms):
                market_sources.append(s)
                if len(market_sources) >= 20:
                    break

    # Recent news sources
    news_sources = []
    if search_terms:
        news_q = await db.execute(
            select(Source)
            .where(Source.signal_type.in_(["news", "engagement"]))
            .order_by(Source.updated_at.desc())
            .limit(500)
        )
        all_news = news_q.scalars().all()
        for s in all_news:
            title_lower = (s.title or "").lower()
            if any(term.lower() in title_lower for term in search_terms):
                news_sources.append(s)
                if len(news_sources) >= 20:
                    break

    # Previous insights for context
    prev_insights_q = await db.execute(
        select(Insight)
        .where(Insight.domain == (interest.category or interest.name))
        .order_by(Insight.created_at.desc())
        .limit(3)
    )
    prev_insights = prev_insights_q.scalars().all()

    return {
        "interest": {
            "id": interest.id,
            "name": interest.name,
            "category": interest.category,
            "region": interest.region,
            "keywords": interest.keywords,
        },
        "indicators": [
            {
                "series_id": i.series_id,
                "name": i.name,
                "value": i.value,
                "unit": i.unit,
                "period": i.period,
                "agency": i.source_agency,
            }
            for i in indicators
        ],
        "market_sources": [
            {
                "id": str(s.id),
                "title": s.title,
                "platform": s.platform,
                "probability": s.current_market_probability,
                "category": s.category,
            }
            for s in market_sources
        ],
        "news_sources": [
            {
                "id": str(s.id),
                "title": s.title,
                "platform": s.platform,
                "sentiment": (s.raw_data or {}).get("sentiment"),
            }
            for s in news_sources
        ],
        "previous_insights": [
            {
                "title": i.title,
                "created_at": str(i.created_at),
                "stale": i.stale,
                "ground_truth": i.ground_truth[:200],
            }
            for i in prev_insights
        ],
    }


@router.post("/collect-indicators")
async def trigger_collect_indicators():
    """Trigger indicator collection from government sources."""
    result = await collect_indicators()
    return {"status": "ok", "results": result}


@router.post("/generate-insights")
async def trigger_generate_insights(db: AsyncSession = Depends(get_db)):
    """Convenience trigger for insight generation.

    Returns the current insight context for all enabled interests.
    Claude Code scheduled task calls this, reasons over the data,
    then POSTs results to /api/insights/.
    """
    from app.models.user_interest import UserInterest

    result = await db.execute(
        select(UserInterest).where(UserInterest.enabled.is_(True))
    )
    interests = result.scalars().all()

    contexts = {}
    for interest in interests:
        domain = interest.category or interest.name
        # Gather indicator summary
        indicator_ids = []
        for spec in interest.indicators or []:
            if ":" in spec:
                _, series_id = spec.split(":", 1)
                indicator_ids.append(series_id)

        ind_q = await db.execute(
            select(Indicator)
            .where(Indicator.series_id.in_(indicator_ids) if indicator_ids else Indicator.id.is_(None))
            .order_by(Indicator.release_date.desc())
            .limit(20)
        )
        indicators = ind_q.scalars().all()

        contexts[domain] = {
            "interest_id": str(interest.id),
            "interest_name": interest.name,
            "region": interest.region,
            "indicator_count": len(indicators),
            "latest_indicators": [
                {"series_id": i.series_id, "name": i.name, "value": i.value, "period": i.period}
                for i in indicators[:5]
            ],
        }

    return {"status": "ok", "domains": contexts}
```

- [ ] **Step 2: Update run-pipeline to include indicator collection**

Find the existing `run_pipeline` endpoint in `meta.py` and add indicator collection to it. Add after the collection step:

```python
    # Collect indicators
    try:
        indicator_result = await collect_indicators()
        results["indicators"] = indicator_result
    except Exception as e:
        results["indicators"] = {"error": str(e)}

    # Note: Insight generation is triggered separately by Claude Code scheduled tasks
    # via POST /api/meta/generate-insights, not inline in the pipeline.
    # This is because insight generation requires LLM reasoning (Claude Code),
    # not just data processing.
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/meta.py
git commit -m "feat: add insight-context and collect-indicators meta endpoints"
```

---

## Task 12: Curate Prediction Market Collection

**Files:**
- Modify: `backend/app/agents/collector/polymarket.py`
- Modify: `backend/app/agents/collector/manifold.py`
- Modify: `backend/app/tasks/prediction_tasks.py`

- [ ] **Step 1: Make Polymarket collection interest-driven**

In `backend/app/agents/collector/polymarket.py`, replace the top-100-by-volume fetch with interest-driven search. The `collect()` method should:

1. Load all enabled UserInterests (not just keywords — also `market_filters`)
2. For each interest, search using `market_filters` and `keywords` via the Gamma API `tag` parameter and slug-based search
3. Remove the default top-100-by-volume fetch (delete the block with `"order": "volume"`)
4. `_get_interest_keywords()` should be updated to also return `market_filters` from UserInterests

The key change is removing or replacing the block that does:
```python
params={"active": "true", "closed": "false", "limit": 100, "order": "volume", "ascending": "false"}
```

Replace with only interest-keyword-driven searches.

- [ ] **Step 2: Make Manifold collection interest-driven**

In `backend/app/agents/collector/manifold.py`, update the `collect()` method:

1. Replace the hardcoded search terms list `["prediction", "technology", "geopolitics", "economy"]` with terms from UserInterest `keywords` and `market_filters` fields
2. Load enabled UserInterests and combine their `keywords` + `market_filters` as search terms
3. Keep the existing Manifold API search mechanism (it's already keyword-based)

- [ ] **Step 3: Fix sports/entertainment filter in prediction_tasks.py**

In `backend/app/tasks/prediction_tasks.py`, replace the keyword-based `_is_sports_or_entertainment()` function. Current signature is `_is_sports_or_entertainment(title: str, slug: str | None) -> bool:`. Change to accept the source object:

```python
def _is_sports_or_entertainment(source) -> bool:
    """Reject sports and entertainment sources using LLM-assigned category."""
    if source.category in ("sports", "entertainment"):
        return True
    # Keep legacy keyword check as fallback for uncategorized sources
    title = (source.title or "").lower()
    slug = ((source.raw_data or {}).get("slug") or "").lower()
    lower = title + " " + slug
    return any(kw in lower for kw in SPORTS_KEYWORDS)
```

Then update the call site (around line 86 in `generate_predictions()`) from:

```python
if _is_sports_or_entertainment(source.title, (source.raw_data or {}).get("slug")):
```

to:

```python
if _is_sports_or_entertainment(source):
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/collector/polymarket.py backend/app/agents/collector/manifold.py backend/app/tasks/prediction_tasks.py
git commit -m "feat: interest-driven market collection, category-based sports filter"
```

---

## Task 13: Default Interest Seed Data

**Files:**
- Create: `backend/app/seed_interests.py`

- [ ] **Step 1: Create seed script**

Create `backend/app/seed_interests.py`:

```python
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
```

- [ ] **Step 2: Test the seed script**

```bash
cd /home/oshrin/projects/future_prediction/backend
python -m app.seed_interests
```

Expected: "Seeded 7 new interests" (or fewer if some already exist).

- [ ] **Step 3: Commit**

```bash
git add backend/app/seed_interests.py
git commit -m "feat: add default interest seed data for 7 domains"
```

---

## Task 14: Frontend Types & API Client Updates

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add new TypeScript types**

Add to `frontend/src/lib/types.ts`:

```typescript
export interface Indicator {
  id: string;
  source_agency: string;
  series_id: string;
  name: string;
  category?: string;
  region?: string;
  value: number;
  unit?: string;
  period: string;
  release_date?: string;
  created_at: string;
}

export interface IndicatorHistory {
  series_id: string;
  agency: string;
  name: string;
  unit?: string;
  data: { period: string; value: number; release_date?: string }[];
}

export interface Insight {
  id: string;
  created_at: string;
  domain: string;
  title: string;
  ground_truth: string;
  trend_analysis: string;
  prediction: string;
  action_items?: string[];
  confidence: string;
  sources?: {
    indicators?: string[];
    market_sources?: string[];
    news_sources?: string[];
  };
  stale: boolean;
}
```

Update existing `UserInterest` interface to include new fields:

```typescript
export interface UserInterest {
  id: string;
  name: string;
  keywords: string[];
  priority: "high" | "medium" | "low";
  category: string;
  active: boolean;
  created_at: string;
  updated_at: string;
  indicators?: string[];
  market_filters?: string[];
  region?: string;
  enabled: boolean;
}
```

- [ ] **Step 2: Add API client functions**

Add to `frontend/src/lib/api.ts`:

```typescript
export async function getIndicators(params?: {
  agency?: string;
  region?: string;
  series_id?: string;
}) {
  const searchParams = new URLSearchParams();
  if (params?.agency) searchParams.set("agency", params.agency);
  if (params?.region) searchParams.set("region", params.region);
  if (params?.series_id) searchParams.set("series_id", params.series_id);
  const qs = searchParams.toString();
  return fetchApi<Indicator[]>(`/api/indicators/${qs ? `?${qs}` : ""}`);
}

export async function getIndicatorHistory(seriesId: string, agency?: string) {
  const qs = agency ? `?agency=${agency}` : "";
  return fetchApi<IndicatorHistory>(`/api/indicators/history/${seriesId}${qs}`);
}

export async function getInsights(domain?: string) {
  const qs = domain ? `?domain=${domain}` : "";
  return fetchApi<Insight[]>(`/api/insights/${qs}`);
}

export async function getInsight(id: string) {
  return fetchApi<Insight>(`/api/insights/${id}`);
}
```

Add the imports for the new types at the top of api.ts.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat: add frontend types and API client for indicators and insights"
```

---

## Task 15: Home Page — Interest-Based Overview

**Files:**
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: Redesign home page**

Update `frontend/src/app/page.tsx` to show an interest-based overview. The page should:

1. Fetch interests (`GET /api/interests`), insights (`GET /api/insights`), and dashboard stats (`GET /api/dashboard/stats`)
2. Display a card per active interest showing:
   - Interest name and region badge
   - Latest insight title + confidence badge (if available)
   - Truncated ground_truth text (first 150 chars)
   - Number of tracked indicators and market sources
3. Keep the existing stats summary bar (total predictions, accuracy, etc.) at the top
4. Add a section below the interest cards for "Recent Insights" — a list of the 5 most recent non-stale insights with their four layers expandable

The existing dashboard data (stats, predictions count, sentiment) remains visible — the interest cards are added as the primary content, not replacing the stats bar.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat: redesign home page with interest-based overview cards"
```

---

## Task 16: Insights Page

**Files:**
- Create: `frontend/src/app/insights/page.tsx`

- [ ] **Step 1: Create insights feed page**

Create `frontend/src/app/insights/page.tsx`:

A reverse-chronological feed of insights, filterable by domain. Each insight card shows:

- Title + confidence badge + domain tag
- Timestamp + stale indicator
- Four collapsible sections: Ground Truth, Trend Analysis, Prediction, Action Items
- Action items rendered as a checklist
- Sources section showing which indicators/markets were used

Use the same styling patterns as existing pages (dark theme, Tailwind, consistent card layout from the predictions page).

- [ ] **Step 2: Add navigation link**

Add "Insights" to the `navItems` array in `frontend/src/components/layout/Sidebar.tsx`. Follow the existing pattern for other nav items (icon, label, href). Use href `/insights`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/insights/page.tsx
git commit -m "feat: add insights feed page with layered analysis display"
```

---

## Task 17: Enhanced Interests Page

**Files:**
- Modify: `frontend/src/app/interests/page.tsx`

- [ ] **Step 1: Enhance interests page with full configuration**

Update `frontend/src/app/interests/page.tsx` to support the new fields:

1. **Form additions:** Add fields for `indicators` (comma-separated series IDs), `market_filters` (comma-separated), `region` (dropdown: IL, US, EU, global), `enabled` toggle
2. **Display additions:** Each interest card shows:
   - Enabled/disabled toggle
   - Region badge
   - List of tracked indicator series
   - List of market filter terms
   - Edit button that opens the form pre-filled
3. **Keep existing:** Name, keywords, priority, category fields remain

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/interests/page.tsx
git commit -m "feat: enhance interests page with indicator and market filter config"
```

---

## Task 18: Interest Detail Page with Charts

**Files:**
- Create: `frontend/src/app/interests/[id]/page.tsx`

- [ ] **Step 1: Install recharts**

```bash
cd /home/oshrin/projects/future_prediction/frontend
npm install recharts
```

- [ ] **Step 2: Create interest detail page**

Create `frontend/src/app/interests/[id]/page.tsx`:

The page shows everything about a single interest:

1. **Header:** Interest name, description, region, enabled status
2. **Indicator charts:** For each indicator series in the interest's `indicators` list, fetch `/api/indicators/history/{series_id}` and render a `LineChart` (recharts) showing value over time with period on x-axis
3. **Market predictions:** Fetch predictions filtered by the interest's keywords, show as a list with probabilities
4. **Latest insight:** If an insight exists for this domain, show the full four-layer view
5. **Configuration:** Show current keywords, indicators, market_filters (read-only, edit on interests page)

Use recharts `LineChart`, `Line`, `XAxis`, `YAxis`, `Tooltip`, `ResponsiveContainer`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/interests/\[id\]/page.tsx
git commit -m "feat: add interest detail page with indicator time-series charts"
```

---

## Task 19: Integration Test — End to End

- [ ] **Step 1: Test indicator collection manually**

```bash
cd /home/oshrin/projects/future_prediction/backend

# Seed interests if not done
python -m app.seed_interests

# Test FRED collection (requires FRED_API_KEY in env)
python -c "
import asyncio
from app.tasks.indicator_tasks import collect_indicators
result = asyncio.run(collect_indicators())
print(result)
"
```

- [ ] **Step 2: Test API endpoints**

```bash
# Start the API
cd /home/oshrin/projects/future_prediction
./dev.sh api &

# Wait for startup, then test
sleep 3
curl -s http://localhost:8000/api/indicators/ | python -m json.tool | head -20
curl -s http://localhost:8000/api/insights/ | python -m json.tool
curl -s http://localhost:8000/api/interests/ | python -m json.tool | head -30

# Test pipeline with indicators
curl -s -X POST http://localhost:8000/api/meta/collect-indicators | python -m json.tool
```

- [ ] **Step 3: Test frontend**

```bash
cd /home/oshrin/projects/future_prediction/frontend
npm run build
```

Expected: no TypeScript errors, build succeeds.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: integration test fixes"
```

---

## Task 20: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update project documentation**

Add to the Architecture section of `CLAUDE.md`:

- Indicator model and government data sources (FRED, CBS Israel, World Bank)
- Insight model with four-layer analysis
- UserInterest as control plane (indicators, market_filters, region, enabled)
- New API endpoints (/api/indicators/, /api/insights/, /api/meta/insight-context/, /api/meta/collect-indicators)
- Updated pipeline description showing dual-track architecture
- Seed script: `python -m app.seed_interests`

Update Data Sources section to include FRED, CBS_IL, WORLD_BANK.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with indicator intelligence platform architecture"
```
