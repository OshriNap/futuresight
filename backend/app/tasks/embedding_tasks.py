"""Cross-source matching via sentence embeddings on local GPU.

Uses all-MiniLM-L6-v2 (~80MB VRAM) to embed source titles, then finds
semantically similar sources across platforms. This enables matching
news/reddit articles to prediction market questions for better signals.
"""

import logging
from collections import defaultdict

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.database import async_session
from app.models.source import Source

logger = logging.getLogger(__name__)

# Lazy-loaded model
_model = None


def _get_model():
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading embedding model on {device}...")
        _model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
        logger.info("Embedding model loaded.")
    return _model


def _compute_embeddings(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """Compute embeddings for a list of texts."""
    model = _get_model()
    return model.encode(texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True)


def _cosine_similarity_batch(query_emb: np.ndarray, corpus_embs: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between a query and corpus (already normalized)."""
    return corpus_embs @ query_emb


async def match_sources(
    similarity_threshold: float = 0.45,
    limit_markets: int = 300,
    limit_news: int = 1000,
) -> dict:
    """Match news/reddit sources to market sources via embedding similarity.

    For each market (Polymarket/Manifold), finds the most semantically
    similar news/reddit sources. Stores matches in raw_data["matched_sources"].

    Returns dict with match counts.
    """
    import asyncio

    async with async_session() as db:
        # Load market sources
        market_result = await db.execute(
            select(Source)
            .where(Source.signal_type == "market_probability")
            .order_by(Source.updated_at.desc())
            .limit(limit_markets)
        )
        markets = market_result.scalars().all()

        # Load news/social sources
        news_result = await db.execute(
            select(Source)
            .where(Source.signal_type.in_(["news", "engagement"]))
            .order_by(Source.updated_at.desc())
            .limit(limit_news)
        )
        news_sources = news_result.scalars().all()

        if not markets or not news_sources:
            return {"markets": len(markets), "news": len(news_sources), "matches": 0}

        # Compute embeddings in thread (GPU work)
        market_titles = [m.title for m in markets]
        news_titles = [n.title for n in news_sources]

        def _embed_all():
            market_embs = _compute_embeddings(market_titles)
            news_embs = _compute_embeddings(news_titles)
            return market_embs, news_embs

        market_embs, news_embs = await asyncio.to_thread(_embed_all)

        # Find matches for each market
        total_matches = 0
        markets_with_matches = 0

        for i, market in enumerate(markets):
            # Compute similarities
            sims = _cosine_similarity_batch(market_embs[i], news_embs)
            top_indices = np.where(sims >= similarity_threshold)[0]

            if len(top_indices) == 0:
                continue

            # Sort by similarity descending, take top 10
            top_indices = top_indices[np.argsort(sims[top_indices])[::-1]][:10]

            matched = []
            for idx in top_indices:
                news = news_sources[idx]
                raw = news.raw_data or {}
                matched.append({
                    "source_id": str(news.id),
                    "platform": news.platform,
                    "title": news.title[:120],
                    "similarity": round(float(sims[idx]), 3),
                    "sentiment": raw.get("sentiment"),
                    "sentiment_label": raw.get("sentiment_label"),
                })

            # Store in market's raw_data
            raw = dict(market.raw_data or {})
            raw["matched_sources"] = matched
            market.raw_data = raw
            flag_modified(market, "raw_data")

            total_matches += len(matched)
            markets_with_matches += 1

        await db.commit()

    logger.info(f"Embedding matching: {markets_with_matches} markets matched, {total_matches} total links")
    return {
        "markets": len(markets),
        "news_sources": len(news_sources),
        "markets_with_matches": markets_with_matches,
        "total_matches": total_matches,
    }
