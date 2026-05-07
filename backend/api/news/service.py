from __future__ import annotations

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


def get_topic_news(topic: str, max_age_hours: int = 168, force: bool = False) -> list[dict]:
    """Return news articles relevant to topic, cached for 30 min.

    Falls back to general AI news when no topic-specific articles are found.
    Pass force=True to bypass the Redis cache and fetch fresh results.
    """
    if not topic or not topic.strip():
        return get_news("ai", force=force)

    import hashlib
    from backend.extensions import get_redis
    r = get_redis()

    topic_hash = hashlib.sha256(topic.lower().encode()).hexdigest()[:10]
    cache_key = f"news:topic:{topic_hash}:{max_age_hours}"

    if not force:
        raw = r.get(cache_key)
        if raw:
            return json.loads(raw)

    articles = fetch_topic_news(topic, max_age_hours=max_age_hours)

    if not articles:
        # No keyword matches — fall back to general AI news
        articles = get_news("ai", force=force)
        clean = [{k: v for k, v in a.items() if k != '_age_hours'} for a in articles]
        r.setex(cache_key, 600, json.dumps(clean))   # 10 min for a miss
    else:
        clean = [{k: v for k, v in a.items() if k != '_age_hours'} for a in articles]
        r.setex(cache_key, 1800, json.dumps(clean))  # 30 min for real matches

    return articles
