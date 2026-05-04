from __future__ import annotations

import logging

from backend.api.news.cache import fetch_and_cache, get_cached
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
