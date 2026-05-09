from __future__ import annotations

import hashlib
import json
import logging

from backend.api.news.cache import fetch_and_cache, fetch_topic_news, get_cached
from backend.api.news.feeds import NEWS_FEEDS

logger = logging.getLogger(__name__)


def get_news(category: str, force: bool = False) -> list[dict]:
    """Return news articles for category, using Redis cache when available."""
    if category not in NEWS_FEEDS:
        return []

    from backend.extensions import get_redis
    r = get_redis()

    if not force:
        cached = get_cached(r, category)
        if cached:
            return cached

    return fetch_and_cache(r, category)


def _infer_category_by_embedding(topic: str) -> str:
    """Pick the NEWS_FEEDS category whose label embedding is closest to the topic.

    Uses the same fastembed model as topic-news ranking — zero-shot classification
    via cosine similarity. No hardcoded keyword lists; tunable by editing
    CATEGORY_LABELS strings in embeddings.py.

    Falls back to 'ai' on any error (missing model, Redis unavailable, etc.).
    """
    try:
        import numpy as np
        from backend.api.news.embeddings import embed, get_category_embeddings
        from backend.extensions import get_redis

        cat_embs = get_category_embeddings(get_redis())
        topic_emb = embed([topic])[0]
        best = max(cat_embs.keys(), key=lambda c: float(np.array(cat_embs[c]) @ topic_emb))
        logger.info("Category inferred for topic '%s': %s", topic[:60], best)
        return best
    except Exception as exc:
        logger.warning("Category embedding inference failed, defaulting to 'ai': %s", exc)
        return "ai"


def get_topic_news(
    topic: str,
    max_age_hours: int = 168,
    force: bool = False,
    source_category: str | None = None,
) -> list[dict]:
    """Return news articles relevant to topic, cached for 30 min.

    Fallback chain when topic-specific search returns no results:
      1. source_category (known fact — set when a news_discussion session is
         created from a specific tab). No inference needed.
      2. Embedding similarity against category label strings (zero-shot
         classification — same model as article ranking, no hardcoding).

    Pass force=True to bypass the Redis cache and fetch fresh results.
    """
    if not topic or not topic.strip():
        fallback = source_category if source_category in NEWS_FEEDS else "ai"
        return get_news(fallback, force=force)

    from backend.extensions import get_redis
    r = get_redis()

    topic_hash = hashlib.sha256(topic.lower().encode()).hexdigest()[:10]
    cache_key = f"news:topic:{topic_hash}:{max_age_hours}"

    if not force:
        raw = r.get(cache_key)
        if raw:
            return json.loads(raw)

    articles = fetch_topic_news(topic, max_age_hours=max_age_hours, force=force)

    if not articles:
        # Step 1: use the session's known source category if available.
        if source_category and source_category in NEWS_FEEDS:
            fallback_cat = source_category
            logger.info("Topic news empty for '%s' — using source_category=%s", topic[:60], fallback_cat)
        else:
            # Step 2: zero-shot category routing via embedding similarity.
            fallback_cat = _infer_category_by_embedding(topic)
            logger.info("Topic news empty for '%s' — embedding-inferred category=%s", topic[:60], fallback_cat)

        articles = get_news(fallback_cat, force=force)
        clean = [{k: v for k, v in a.items() if k != '_age_hours'} for a in articles]
        r.setex(cache_key, 600, json.dumps(clean))   # 10 min for a miss
    else:
        clean = [{k: v for k, v in a.items() if k != '_age_hours'} for a in articles]
        r.setex(cache_key, 1800, json.dumps(clean))  # 30 min for real matches

    return articles
