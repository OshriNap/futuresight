"""Data collection tasks - called via API endpoints."""

import logging

logger = logging.getLogger(__name__)


async def _run_sentiment(platform: str | None = None) -> dict | None:
    """Run sentiment analysis on newly collected sources. Skips if GPU deps not installed."""
    try:
        from app.tasks.sentiment_tasks import analyze_sentiment
        result = await analyze_sentiment(platform=platform, batch_size=32, limit=500)
        logger.info(f"Sentiment ({platform or 'all'}): {result}")
        return result
    except ImportError:
        logger.debug("Skipping sentiment: torch/transformers not installed")
        return None
    except Exception as e:
        logger.warning(f"Sentiment analysis failed: {e}")
        return None


async def collect_polymarket(skip_sentiment: bool = False) -> dict:
    from app.agents.collector.polymarket import PolymarketCollector

    collector = PolymarketCollector()
    items = await collector.collect()
    saved = await collector.save_items(items)
    sentiment = None if skip_sentiment else await _run_sentiment("polymarket")
    logger.info(f"Polymarket: collected {len(items)}, saved {saved}")
    return {"collected": len(items), "saved": saved, "sentiment": sentiment}


async def collect_gdelt(skip_sentiment: bool = False) -> dict:
    from app.agents.collector.news_gdelt import GdeltNewsCollector

    collector = GdeltNewsCollector()
    items = await collector.collect()
    saved = await collector.save_items(items)
    sentiment = None if skip_sentiment else await _run_sentiment("gdelt")
    logger.info(f"GDELT: collected {len(items)}, saved {saved}")
    return {"collected": len(items), "saved": saved, "sentiment": sentiment}


async def collect_manifold(skip_sentiment: bool = False) -> dict:
    from app.agents.collector.manifold import ManifoldCollector

    collector = ManifoldCollector()
    items = await collector.collect()
    saved = await collector.save_items(items)
    sentiment = None if skip_sentiment else await _run_sentiment("manifold")
    logger.info(f"Manifold: collected {len(items)}, saved {saved}")
    return {"collected": len(items), "saved": saved, "sentiment": sentiment}


async def collect_reddit(skip_sentiment: bool = False) -> dict:
    from app.agents.collector.reddit import RedditWorldNewsCollector

    collector = RedditWorldNewsCollector()
    items = await collector.collect()
    saved = await collector.save_items(items)
    sentiment = None if skip_sentiment else await _run_sentiment("reddit")
    logger.info(f"Reddit: collected {len(items)}, saved {saved}")
    return {"collected": len(items), "saved": saved, "sentiment": sentiment}


async def collect_all() -> dict:
    """Run all collectors, then score sentiment in one batch."""
    results = {}
    for name, fn in [("polymarket", collect_polymarket), ("manifold", collect_manifold), ("gdelt", collect_gdelt), ("reddit", collect_reddit)]:
        try:
            results[name] = await fn(skip_sentiment=True)
        except Exception as e:
            logger.error(f"Collector {name} failed: {e}")
            results[name] = {"error": str(e)}

    # Single sentiment pass across all new sources
    results["sentiment"] = await _run_sentiment()
    return results
