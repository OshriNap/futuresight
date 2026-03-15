"""Batch sentiment analysis using local GPU.

Uses cardiffnlp/twitter-roberta-base-sentiment for fast, deterministic
sentiment classification. Processes sources in batches and stores scores
in the source raw_data.
"""

import logging

from sqlalchemy import select

from app.database import async_session
from app.models.source import Source

logger = logging.getLogger(__name__)

# Lazy-loaded model (stays in GPU memory across calls)
_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        import torch
        from transformers import pipeline

        device = 0 if torch.cuda.is_available() else -1
        logger.info(f"Loading sentiment model on {'GPU' if device == 0 else 'CPU'}...")
        _pipeline = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            device=device,
            truncation=True,
            max_length=512,
        )
        logger.info("Sentiment model loaded.")
    return _pipeline


def _score_to_float(label: str, score: float) -> float:
    """Convert model output to [-1, 1] range."""
    if label == "positive":
        return score
    elif label == "negative":
        return -score
    else:  # neutral
        return 0.0


async def analyze_sentiment(
    platform: str | None = None,
    batch_size: int = 32,
    limit: int = 500,
    force: bool = False,
) -> dict:
    """Run sentiment analysis on sources that don't have scores yet.

    Args:
        platform: Filter by platform (gdelt, reddit, or None for all)
        batch_size: Number of texts to process at once
        limit: Max sources to process
        force: Re-analyze even if sentiment already exists

    Returns:
        Dict with counts of processed/skipped sources.
    """
    import asyncio

    async with async_session() as db:
        # Get sources to analyze
        query = select(Source).order_by(Source.updated_at.desc()).limit(limit)
        if platform:
            query = query.where(Source.platform == platform)

        result = await db.execute(query)
        sources = result.scalars().all()

        # Filter to those without sentiment (unless force)
        to_analyze = []
        for s in sources:
            raw = s.raw_data or {}
            if not force and "sentiment" in raw:
                continue
            # Need text to analyze
            text = s.title
            if s.description and len(s.description) > 20:
                text = f"{s.title}. {s.description[:300]}"
            if len(text) < 10:
                continue
            to_analyze.append((s, text))

        if not to_analyze:
            return {"processed": 0, "skipped": len(sources), "message": "All sources already have sentiment scores"}

        # Process in batches on GPU (run in thread to not block event loop)
        def _run_batch():
            pipe = _get_pipeline()
            texts = [text for _, text in to_analyze]
            results = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_results = pipe(batch)
                results.extend(batch_results)

            return results

        sentiment_results = await asyncio.to_thread(_run_batch)

        # Save results back to sources
        from sqlalchemy.orm.attributes import flag_modified

        processed = 0
        for (source, _), result in zip(to_analyze, sentiment_results):
            raw = dict(source.raw_data or {})
            raw["sentiment"] = _score_to_float(result["label"], result["score"])
            raw["sentiment_label"] = result["label"]
            raw["sentiment_confidence"] = round(result["score"], 4)
            source.raw_data = raw
            flag_modified(source, "raw_data")
            processed += 1

        await db.commit()

    logger.info(f"Sentiment analysis: processed={processed}, skipped={len(sources) - len(to_analyze)}")
    return {
        "processed": processed,
        "skipped": len(sources) - len(to_analyze),
        "total_sources": len(sources),
    }
