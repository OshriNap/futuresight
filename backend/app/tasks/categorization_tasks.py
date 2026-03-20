"""Categorization — classifies sources using local GPU zero-shot classifier.

Uses the NLI model (cross-encoder/nli-distilroberta-base) via HuggingFace
zero-shot-classification pipeline. Fast, deterministic, no external API needed.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.database import async_session
from app.models.source import Source

logger = logging.getLogger(__name__)

VALID_CATEGORIES = [
    "politics", "geopolitics", "economy", "finance", "technology",
    "climate", "health", "sports", "entertainment", "science", "general",
]

BATCH_SIZE = 32

# Lazy-loaded model (stays in GPU memory across calls)
_classifier = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        import torch
        from transformers import pipeline

        device = 0 if torch.cuda.is_available() else -1
        logger.info(f"Loading zero-shot classifier on {'GPU' if device == 0 else 'CPU'}...")
        _classifier = pipeline(
            "zero-shot-classification",
            model="cross-encoder/nli-distilroberta-base",
            device=device,
        )
        logger.info("Zero-shot classifier loaded.")
    return _classifier


async def categorize_sources(limit: int = 0) -> dict:
    """Categorize uncategorized sources using local GPU zero-shot classifier.

    Args:
        limit: Max sources to categorize. 0 = all uncategorized.

    Returns:
        Dict with counts per category and total categorized.
    """
    async with async_session() as db:
        query = (
            select(Source)
            .where(Source.category.is_(None))
            .options(load_only(Source.id, Source.title, Source.category))
        )
        if limit > 0:
            query = query.limit(limit)

        result = await db.execute(query)
        sources = result.scalars().all()

        if not sources:
            return {"categorized": 0, "message": "No uncategorized sources"}

        logger.info(f"Categorizing {len(sources)} sources via zero-shot classifier")

        classifier = _get_classifier()
        categorized = 0
        failed = 0
        category_counts: dict[str, int] = {}

        # Exclude 'general' from candidate labels — use it as fallback
        candidate_labels = [c for c in VALID_CATEGORIES if c != "general"]

        for i in range(0, len(sources), BATCH_SIZE):
            batch = sources[i:i + BATCH_SIZE]
            titles = [s.title or "" for s in batch]

            try:
                results = classifier(titles, candidate_labels, multi_label=False)
                if not isinstance(results, list):
                    results = [results]

                for source, res in zip(batch, results):
                    top_label = res["labels"][0]
                    top_score = res["scores"][0]

                    # Use category if confidence > 0.3, otherwise 'general'
                    cat = top_label if top_score > 0.3 else "general"
                    source.category = cat
                    category_counts[cat] = category_counts.get(cat, 0) + 1
                    categorized += 1

            except Exception as e:
                logger.warning(f"Batch {i // BATCH_SIZE} failed: {e}")
                failed += len(batch)

            if (i + BATCH_SIZE) % (BATCH_SIZE * 10) == 0:
                logger.info(f"  Progress: {i + BATCH_SIZE}/{len(sources)}")

        await db.commit()

    logger.info(f"Categorized {categorized} sources, {failed} failed")
    return {
        "categorized": categorized,
        "failed": failed,
        "categories": category_counts,
    }
