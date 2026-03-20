# Indicator-Driven Intelligence Platform

**Date:** 2026-03-20
**Status:** Draft
**Scope:** Phase B — Dual-track system (indicators + curated markets)

## Problem

The prediction platform currently pulls the top 100 markets by betting volume from Polymarket, producing ~985 predictions dominated by sports matches and trivial topics. The sports filter catches only ~50% of sports content (pattern-based on titles, ignores the category field). UserInterest exists but only supplements collection — it doesn't constrain it. The result: predictions that are technically accurate but produce no actionable insight. Everything is "so what?"

## Solution

Transform the platform from "what are people betting on?" to "what's actually happening in the world, what does it mean, and what might happen next?" by:

1. Adding government statistical data as primary grounding sources
2. Making UserInterest the control plane that drives all collection
3. Curating prediction markets to macro/geopolitics/tech only
4. Generating layered insights (data → trend → prediction → action items)

## Design

### 1. Data Model Changes

#### New Model: `Indicator`

Time-series data points from official statistical agencies.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `created_at` | datetime | Record creation time |
| `updated_at` | datetime | Last update time |
| `source_agency` | string | Agency identifier: "CBS_IL", "BLS_US", "FRED", "WORLD_BANK" |
| `series_id` | string | Agency's own series identifier (e.g., FRED's "UNRATE") |
| `name` | string | Human-readable name (e.g., "US Unemployment Rate") |
| `category` | string | Domain category (economy, technology, climate, etc.) |
| `region` | string | Geographic region: "IL", "US", "EU", "global" |
| `value` | float | The numeric value |
| `unit` | string | Unit of measurement: "percent", "index", "thousands", "usd", etc. |
| `period` | string | Time period covered: "2025-Q4", "2026-01", "2026-W12" |
| `release_date` | date | When the agency published this data point |
| `metadata` | JSON | Extra context (seasonal adjustment, revision status, etc.) |

Unique constraint: `(source_agency, series_id, period)` — one value per series per period.

Additional index: `(series_id, release_date)` for efficient time-series history queries.

#### New Model: `Insight`

LLM-generated layered analysis connecting indicators, markets, and news.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `created_at` | datetime | When the insight was generated |
| `domain` | string | Links to UserInterest category |
| `title` | string | e.g., "Israeli Housing Market Cooling Signal" |
| `ground_truth` | text | Layer 1: What the data says (facts, numbers) |
| `trend_analysis` | text | Layer 2: What's changing and why |
| `prediction` | text | Layer 3: What might happen next |
| `action_items` | JSON | Layer 4: List of actionable considerations |
| `confidence` | string | Overall confidence: "low", "medium", "high" |
| `sources` | JSON | Structured references: `{"indicators": [uuid, ...], "market_sources": [uuid, ...], "news_sources": [uuid, ...]}` |
| `stale` | boolean | Set to true when underlying data gets updated |

#### Changes to `UserInterest`

| Field | Type | Description |
|-------|------|-------------|
| `indicators` | JSON | List of series IDs to track (e.g., `["CBS_IL:cpi", "FRED:UNRATE"]`) |
| `market_filters` | JSON | Keywords/slugs for market search (e.g., `["israel", "shekel"]`) |
| `region` | string | Geographic focus: "IL", "US", "EU", "global" |
| `enabled` | boolean | Toggle interest on/off (controls collection). Distinct from existing `notification_enabled` which will control alerts in Phase C. |

Existing fields (`name`, `description`, `keywords`, `category`, `priority`, `notification_enabled`) remain unchanged. Pydantic schemas (`InterestCreate`, `InterestUpdate` in `api/interests.py`) and the frontend TypeScript `UserInterest` type (`frontend/src/lib/types.ts`) must be updated to include the new fields.

### 2. Government Data Collectors

Indicator collectors do **not** extend `BaseCollector` (which is hardcoded to write `Source` + `PriceSnapshot` records). Instead, they share a new `BaseIndicatorCollector` base class that writes to the `Indicator` table. This base class provides:
- `async def collect(self) -> list[IndicatorRecord]` — abstract method each collector implements
- `async def save_indicators(self, records: list[IndicatorRecord])` — upserts to Indicator table using the `(source_agency, series_id, period)` unique constraint
- Standard retry logic (3 retries with exponential backoff) for flaky government APIs
- Logging consistent with existing collectors

#### FRED (Federal Reserve Economic Data)

- **API:** `api.stlouisfed.org/fred/series/observations` — free, requires API key (free registration at fredaccount.stlouisfed.org)
- **Coverage:** GDP, unemployment (UNRATE), CPI (CPIAUCSL), Fed funds rate (FEDFUNDS), housing starts (HOUST), consumer confidence (UMCSENT), 10Y treasury (DGS10), and thousands more
- **Update frequency:** Varies per series (weekly to quarterly)
- **Collection strategy:** Pull only series listed in UserInterest `indicators` fields where `source_agency` starts with "FRED"
- **Rate limits:** 120 requests/minute (generous)

#### CBS Israel (הלשכה המרכזית לסטטיסטיקה)

- **API:** CBS provides data via their SOAP/XML API at `apis.cbs.gov.il` and downloadable CSV/Excel files from `cbs.gov.il`. There is no simple REST JSON endpoint.
- **Implementation approach:** Use the CBS tabular data endpoint which returns structured data. Parse XML responses and normalize into Indicator records. Fall back to CSV downloads for series not available via the API.
- **Coverage:** CPI, housing price index, unemployment, construction starts, immigration, trade balance, wage index
- **Update frequency:** Mostly monthly, some quarterly. Data delayed ~4-6 weeks.
- **Collection strategy:** Pull series mapped in UserInterest `indicators` fields where `source_agency` is "CBS_IL"
- **Notes:** Hebrew + English series names. Series IDs will use CBS's own numbering system (e.g., `CBS_IL:price_index_housing`). May require some manual mapping during initial setup.
- **Risk:** CBS API is less developer-friendly than FRED. If integration proves too brittle, Israeli economic data is partially available via FRED (e.g., `IRLTLT01ILM156N` for Israel long-term interest rates) and Bank of Israel's more modern API (Phase C candidate).

#### World Bank Open Data

- **API:** `api.worldbank.org/v2/country/{code}/indicator/{indicator}?format=json` — free, no key needed
- **Coverage:** GDP per capita, poverty rates, trade volumes, energy consumption, health indicators across all countries
- **Update frequency:** Mostly annual (lagging but reliable for grounding)
- **Collection strategy:** Pull country+indicator combos from UserInterest configuration where `source_agency` is "WORLD_BANK"
- **Use case:** Global context and cross-country comparisons

#### Deferred to Phase C
Eurostat, IMF, OECD, Bank of Israel direct API.

#### Series ID Format

The `indicators` field in UserInterest uses the format `{source_agency}:{series_id}` where:
- `source_agency` is one of: `FRED`, `CBS_IL`, `WORLD_BANK`
- `series_id` is the agency's own identifier

Examples: `FRED:UNRATE`, `FRED:CPIAUCSL`, `CBS_IL:price_index_housing`, `WORLD_BANK:NY.GDP.MKTP.CD`

Validation: when saving a UserInterest, each indicator string must match an agency prefix. The collector for that agency is responsible for resolving the series_id to an actual API call. Invalid series IDs will produce a warning log during collection but won't block other series.

#### Seed Series Catalog

Default interests ship with these concrete indicator series:

| Interest | Indicators |
|----------|-----------|
| Israeli Economy | `FRED:IRLTLT01ILM156N` (IL interest rates), `CBS_IL:cpi`, `CBS_IL:housing_price_index`, `CBS_IL:unemployment_rate`, `CBS_IL:construction_starts` |
| US Economy | `FRED:UNRATE`, `FRED:CPIAUCSL`, `FRED:GDP`, `FRED:FEDFUNDS`, `FRED:UMCSENT`, `FRED:HOUST` |
| Global Financial Markets | `FRED:DGS10` (10Y treasury), `FRED:VIXCLS` (VIX), `FRED:DCOILWTICO` (WTI crude), `WORLD_BANK:NY.GDP.MKTP.CD` |

Interests without indicators (Geopolitics, AI & Tech, Climate) rely on news + market sources only.

### 3. Curated Prediction Markets

#### Collection Changes

**Before:** Polymarket fetches top 100 by volume (indiscriminate). UserInterest supplements.

**After:**
- Polymarket: use the Gamma API `tag` parameter for each UserInterest `market_filters` entry, plus text search via the `/markets` endpoint with `slug` matching for keyword-based filtering. No more top-N-by-volume default fetch.
- Manifold: use their existing search endpoint (already keyword-based in the current collector), driven by UserInterest `market_filters` and `keywords`
- No more top-N-by-volume firehose
- After LLM categorization (existing Ollama-based system), hard-reject any source with `category` in `["sports", "entertainment"]`
- Keep existing liquidity floor to filter dead markets
- Expected result: ~50-150 high-relevance markets instead of ~1,300

#### How Markets and Indicators Complement Each Other

- Indicators provide ground truth: "CBS says unemployment is 3.5%"
- Markets provide crowd expectations: "Polymarket gives 65% chance it exceeds 4% by Q4"
- The gap between the two is where interesting insights live

### 4. Insight Generation

#### Process

A scheduled Claude Code task (daily + on-demand via API):

1. Groups recent indicators + relevant market sources by UserInterest domain
2. For each domain with new or updated data, generates an `Insight` with four layers:

```
Layer 1 — Ground Truth: "Israeli CPI rose 0.4% in February, 3.2% YoY.
          Housing component up 0.7%. CBS construction starts down 12% QoQ."

Layer 2 — Trend Analysis: "Third consecutive month of above-target inflation.
          Housing supply contracting while prices accelerate. Bank of Israel
          held rates at 4.5% despite pressure."

Layer 3 — Prediction: "Inflation likely to remain sticky through Q2.
          Polymarket gives 40% chance of rate hike by June. If construction
          starts don't recover, housing prices may accelerate further."

Layer 4 — Action Items:
          - "Fixed-rate mortgage locks increasingly attractive"
          - "Israeli real estate REITs may benefit short-term but face rate risk"
          - "Watch March CPI release (expected April 15) for confirmation"
```

#### Triggers

- New indicator data arrives (e.g., CBS publishes new CPI)
- Significant market probability shift (>10% move on a tracked market)
- Scheduled weekly synthesis even without new data (trend check)

#### Staleness

When new indicator data arrives, existing insights that referenced the old data get `stale=True`. Next generation cycle replaces them.

#### Implementation

All LLM reasoning via Claude Code scheduled tasks — same pattern as existing meta agents.

**API round-trip flow:**
1. Claude Code task calls `GET /api/meta/insight-context/{interest_id}` — returns recent indicators, market sources, news, and existing insights for that interest domain
2. Claude Code performs the layered reasoning
3. Claude Code calls `POST /api/insights/` with the generated insight (title, four layers, confidence, source references)
4. The API validates and saves the Insight record, marking any previous insights for the same domain as `stale=True`

The `POST /api/meta/generate-insights` endpoint is a convenience trigger that can be called manually or by the pipeline — it simply signals the scheduled task to run.

### 5. UserInterest as Control Plane

UserInterest shifts from decoration to the central configuration driving the entire system.

#### Flow

1. User adds interest via UI or API (e.g., name="Israeli Economy", category="economy", region="IL")
2. User configures what to track:
   - `keywords`: `["Israel economy", "Israeli inflation", "Bank of Israel"]` — drives market search, GDELT, Reddit
   - `indicators`: `["CBS_IL:cpi", "CBS_IL:housing_prices", "CBS_IL:unemployment"]` — specific series
   - `market_filters`: `["israel", "bank-of-israel", "shekel"]` — Polymarket/Manifold search terms
3. All collectors use UserInterest as **primary input**, not supplementary
4. Insights are generated per-interest domain

#### Default Interests

Shipped as seed data, user can add/remove anytime:

| Interest | Region | Key Indicators |
|----------|--------|---------------|
| Israeli Economy | IL | CPI, housing prices, employment, BoI rate |
| US Economy | US | GDP, unemployment, CPI, Fed rate, consumer confidence |
| Geopolitics — Middle East | global | — (news + markets only) |
| Geopolitics — US-China | global | — (news + markets only) |
| AI & Technology | global | — (news + markets only) |
| Climate & Energy | global | — (news + markets only) |
| Global Financial Markets | global | Treasury yields, VIX, commodity indices |

### 6. Frontend Changes

#### What Stays (Unchanged)

- Predictions page (now shows only curated markets)
- Accuracy/comparison page (prediction method comparison)
- Evolution page (strategy evolution system)
- Agents page
- Event graph page
- Scratchpad

#### What Changes

**Home page:** Shifts from binary prediction list to interest-based overview — cards per active interest showing latest indicator values, trend direction (up/down/flat arrows), and most recent insight summary.

**Interests page:** Enhanced from simple CRUD to full configuration — add/remove interests, configure indicators and market filters per interest, see tracked data series, toggle on/off.

#### What's New

**Interest detail page:** Click into an interest to see indicator time-series charts, relevant curated market predictions, full layered insights, historical data.

**Insights page:** Reverse-chronological feed of generated insights, filterable by domain/interest.

**Charts:** Lightweight time-series charts for indicators using **recharts** (React-native, better Next.js integration than chart.js).

### 7. API Endpoints

New endpoints under existing router structure:

#### Indicators
- `GET /api/indicators/` — list indicators, filter by agency/category/region
- `GET /api/indicators/{series_id}/history` — time-series for a specific indicator
- `POST /api/meta/collect-indicators` — trigger indicator collection

#### Insights
- `GET /api/insights/` — list insights, filter by domain, exclude stale
- `GET /api/insights/{id}` — single insight detail
- `POST /api/insights/` — create a new insight (used by Claude Code scheduled task to write back results)
- `GET /api/meta/insight-context/{interest_id}` — gather indicators, markets, news for an interest (data for Claude Code to reason over)
- `POST /api/meta/generate-insights` — trigger insight generation cycle

#### Updated
- `POST /api/meta/run-pipeline` — extended to include indicator collection and insight generation

### 8. Migration Strategy

Existing data (Sources, Predictions, PredictionScores) is **kept as-is**. No deletion or archival.

- Old Source records from the firehose approach remain in the database for historical reference
- Existing PredictionScores continue to feed the tool performance weighting system (tools need 5+ scored predictions for performance-based selection — losing this data would reset the evolution system)
- The collection change is forward-only: new collection runs use interest-driven logic, but old data is not retroactively filtered
- Old predictions will naturally age out as markets resolve and new curated predictions replace them

### 9. Pipeline

```
collect indicators (FRED/CBS/WB) ──────────────────────────────────┐
                                                                    │
collect markets (curated) ─→ categorize (Ollama) ─→ filter ────────┤
                                        │                          │
collect news (GDELT) ──────────────────┤                          │
                                        │                          │
collect social (Reddit) ───────────────┘                          │
                                        │                          │
                              sentiment (GPU) ─→ match (GPU) ─→ graph
                                        │                          │
                                        ▼                          ▼
                              predict ─→ score/evolve    generate insights
                              (8 tools, unchanged)       (Claude Code task)
```

The existing pipeline (categorize → sentiment → match → graph → predict → score) runs unchanged for market sources. Indicator collection and insight generation run as a parallel track. Both tracks feed the frontend.

## What's NOT in Scope (Phase C)

- Cross-domain correlation engine
- Alert system with configurable thresholds
- Daily/weekly digest generation (email/Telegram)
- Structured action items with confidence scoring
- Additional government sources (Eurostat, IMF, OECD, BoI)
- Push notifications on significant shifts
