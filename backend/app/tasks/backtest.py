"""Backtesting — evaluate prediction tools against resolved markets.

Fetches resolved markets from Manifold, runs each tool independently,
and compares predictions to actual outcomes. Produces per-tool Brier
scores and a head-to-head comparison.
"""

import logging
import math
from collections import defaultdict
from dataclasses import dataclass

import httpx

from app.tools.base_tool import ToolInput, ToolOutput
from app.tools.tool_registry import registry

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    question: str
    category: str
    resolution: str  # YES or NO
    actual: float  # 1.0 or 0.0
    market_prob: float  # last market probability
    tool_predictions: dict[str, float]  # tool_name -> predicted probability


async def fetch_resolved_markets(
    search_terms: list[str] | None = None,
    min_bettors: int = 5,
    max_markets: int = 200,
) -> list[dict]:
    """Fetch resolved binary markets from Manifold with midpoint probabilities.

    Uses bet history to find the probability at ~midpoint of market life,
    NOT the final probability (which converges to 0/1 and is trivial to predict).
    """
    if search_terms is None:
        search_terms = [
            "AI", "technology", "politics", "economy", "climate",
            "war", "election", "quantum", "crypto", "regulation",
            "China", "Russia", "president", "GDP", "inflation",
        ]

    all_markets = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(timeout=30) as client:
        for term in search_terms:
            try:
                r = await client.get(
                    "https://api.manifold.markets/v0/search-markets",
                    params={
                        "term": term,
                        "filter": "resolved",
                        "sort": "liquidity",
                        "limit": 30,
                    },
                )
                r.raise_for_status()
                for m in r.json():
                    mid = m.get("id")
                    if mid and mid not in seen_ids:
                        seen_ids.add(mid)
                        all_markets.append(m)
            except httpx.HTTPError as e:
                logger.warning(f"Manifold search failed for '{term}': {e}")

    # Filter to usable markets
    # Skip meta/trick/self-resolving markets that poison backtests
    JUNK_KEYWORDS = [
        "self-resolving", "this market", "will this question",
        "will the market", "resolve yes", "resolve no",
        "mana", "manifold", "will i ",
    ]

    good = []
    for m in all_markets:
        if m.get("resolution") not in ("YES", "NO"):
            continue
        if m.get("outcomeType") != "BINARY":
            continue
        if m.get("uniqueBettorCount", 0) < min_bettors:
            continue
        if m.get("probability") is None:
            continue
        # Filter junk/meta markets
        q_lower = m.get("question", "").lower()
        if any(kw in q_lower for kw in JUNK_KEYWORDS):
            continue
        good.append(m)

    good.sort(key=lambda m: m.get("uniqueBettorCount", 0), reverse=True)
    good = good[:max_markets]

    # Fetch midpoint probabilities from bet history
    logger.info(f"Fetching midpoint probabilities for {len(good)} markets...")
    async with httpx.AsyncClient(timeout=30) as bet_client:
        for m in good:
            mid = m["id"]
            try:
                r = await bet_client.get(
                    "https://api.manifold.markets/v0/bets",
                    params={"contractId": mid, "limit": 200, "order": "asc"},
                )
                if r.status_code == 200:
                    bets = r.json()
                    if bets:
                        # Use probability at ~40% through market life (before convergence)
                        midpoint_idx = max(0, len(bets) * 2 // 5 - 1)
                        m["midpoint_prob"] = bets[midpoint_idx].get("probAfter", m["probability"])
                        m["opening_prob"] = bets[0].get("probBefore", 0.5)
                        m["total_bets"] = len(bets)
                    else:
                        m["midpoint_prob"] = m["probability"]
                        m["opening_prob"] = 0.5
                        m["total_bets"] = 0
            except Exception:
                m["midpoint_prob"] = m["probability"]
                m["opening_prob"] = 0.5
                m["total_bets"] = 0

    return good


def _guess_category(title: str) -> str:
    lower = title.lower()
    if any(w in lower for w in ["bitcoin", "ethereum", "crypto", "stock", "price"]):
        return "finance"
    if any(w in lower for w in ["election", "president", "senate", "democrat", "republican", "vote"]):
        return "politics"
    if any(w in lower for w in ["war", "invasion", "sanction", "military", "nato", "nuclear", "russia", "china"]):
        return "geopolitics"
    if any(w in lower for w in ["ai", "quantum", "openai", "google", "tech", "software", "gpt"]):
        return "technology"
    if any(w in lower for w in ["climate", "temperature", "weather"]):
        return "climate"
    if any(w in lower for w in ["gdp", "inflation", "fed", "interest rate", "recession"]):
        return "economy"
    return "general"


async def run_backtest(
    min_bettors: int = 5,
    max_markets: int = 200,
    search_terms: list[str] | None = None,
) -> dict:
    """Run backtesting against resolved markets.

    For each resolved market, runs every applicable tool independently
    (not ensembled) and records its prediction. Then scores each tool
    against the actual outcome.

    Returns comprehensive performance analysis.
    """
    logger.info("Fetching resolved markets for backtesting...")
    markets = await fetch_resolved_markets(search_terms, min_bettors, max_markets)

    if not markets:
        return {"error": "No resolved markets found", "markets": 0}

    logger.info(f"Backtesting against {len(markets)} resolved markets...")

    results: list[BacktestResult] = []
    tool_names = [t.name for t in registry.list_tools()]

    for market in markets:
        question = market.get("question", "")
        # Use MIDPOINT probability (not final, which converges to 0/1)
        prob = market.get("midpoint_prob", market.get("probability", 0.5))
        resolution = market["resolution"]
        actual = 1.0 if resolution == "YES" else 0.0
        category = _guess_category(question)
        volume = market.get("volume", 0)

        # Build tool input (simulating what we'd have at prediction time)
        signals = {
            "market_probability": prob,
            "market_volume": volume,
        }

        tool_input = ToolInput(
            question=question,
            category=category,
            current_signals=signals,
            time_horizon="medium",
        )

        # Run each tool independently
        tool_preds = {}
        for name in tool_names:
            tool = registry.get_tool(name)
            if not tool:
                continue
            can, _ = tool.can_handle(tool_input)
            if not can:
                continue
            try:
                output = await tool.predict(tool_input)
                tool_preds[name] = output.probability
            except Exception as e:
                logger.debug(f"Tool {name} failed on '{question[:40]}': {e}")

        # Run ensemble
        tool_names_for_ensemble = registry.select_tools(tool_input)
        ensemble_results = await registry.run_tools(tool_input, tool_names_for_ensemble)
        if ensemble_results:
            ensemble_output = registry.ensemble_prediction(ensemble_results)
            tool_preds["_ENSEMBLE"] = ensemble_output.probability

        # Baselines
        tool_preds["_NAIVE_50"] = 0.5

        results.append(BacktestResult(
            question=question,
            category=category,
            resolution=resolution,
            actual=actual,
            market_prob=prob,
            tool_predictions=tool_preds,
        ))

    # === Analysis ===

    # Per-tool Brier scores
    tool_briers: dict[str, list[float]] = defaultdict(list)
    tool_log_losses: dict[str, list[float]] = defaultdict(list)
    tool_correct: dict[str, int] = defaultdict(int)
    tool_total: dict[str, int] = defaultdict(int)

    # Also track the raw market as a baseline
    market_briers = []

    for r in results:
        # Market baseline
        market_brier = (r.market_prob - r.actual) ** 2
        market_briers.append(market_brier)

        for tool_name, pred in r.tool_predictions.items():
            brier = (pred - r.actual) ** 2
            tool_briers[tool_name].append(brier)

            # Log loss (clamp to avoid log(0))
            p = max(0.01, min(0.99, pred))
            ll = -(r.actual * math.log(p) + (1 - r.actual) * math.log(1 - p))
            tool_log_losses[tool_name].append(ll)

            # Accuracy (did it predict the right direction?)
            predicted_yes = pred >= 0.5
            actual_yes = r.actual >= 0.5
            tool_total[tool_name] += 1
            if predicted_yes == actual_yes:
                tool_correct[tool_name] += 1

    # Build per-tool summary
    tool_summary = {}
    for name in sorted(tool_briers.keys()):
        briers = tool_briers[name]
        avg_brier = sum(briers) / len(briers)
        avg_ll = sum(tool_log_losses[name]) / len(tool_log_losses[name])
        accuracy = tool_correct[name] / max(tool_total[name], 1) * 100
        tool_summary[name] = {
            "avg_brier": round(avg_brier, 4),
            "avg_log_loss": round(avg_ll, 4),
            "accuracy_pct": round(accuracy, 1),
            "n_predictions": len(briers),
        }

    # Market baseline
    market_avg_brier = sum(market_briers) / len(market_briers) if market_briers else None

    # Per-category analysis
    cat_data: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        for tool_name, pred in r.tool_predictions.items():
            brier = (pred - r.actual) ** 2
            cat_data[r.category][tool_name].append(brier)

    category_summary = {}
    for cat, tools in sorted(cat_data.items()):
        category_summary[cat] = {
            tool: round(sum(scores) / len(scores), 4)
            for tool, scores in sorted(tools.items())
        }

    # Find best/worst examples
    best_calls = []
    worst_calls = []
    for r in results:
        if "market_consensus" in r.tool_predictions:
            pred = r.tool_predictions["market_consensus"]
            brier = (pred - r.actual) ** 2
            best_calls.append((brier, pred, r))
            worst_calls.append((brier, pred, r))

    best_calls.sort(key=lambda x: x[0])
    worst_calls.sort(key=lambda x: -x[0])

    # Rank tools
    ranked = sorted(tool_summary.items(), key=lambda x: x[1]["avg_brier"])

    return {
        "total_markets": len(results),
        "yes_count": sum(1 for r in results if r.actual == 1.0),
        "no_count": sum(1 for r in results if r.actual == 0.0),
        "market_baseline_brier": round(market_avg_brier, 4) if market_avg_brier else None,
        "tool_ranking": [
            {"rank": i + 1, "tool": name, **stats}
            for i, (name, stats) in enumerate(ranked)
        ],
        "category_brier": category_summary,
        "best_predictions": [
            {
                "question": r.question[:80],
                "predicted": round(pred, 3),
                "actual": r.resolution,
                "brier": round(brier, 4),
            }
            for brier, pred, r in best_calls[:5]
        ],
        "worst_predictions": [
            {
                "question": r.question[:80],
                "predicted": round(pred, 3),
                "actual": r.resolution,
                "brier": round(brier, 4),
            }
            for brier, pred, r in worst_calls[:5]
        ],
    }
