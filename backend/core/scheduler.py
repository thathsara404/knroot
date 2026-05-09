from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from backend.api.news.cache import promote_hour_to_day
from backend.api.news.feeds import NEWS_FEEDS

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def init_scheduler(redis_client) -> BackgroundScheduler:
    global _scheduler
    _scheduler = BackgroundScheduler()

    def _promote_all():
        for category in NEWS_FEEDS:
            try:
                promote_hour_to_day(redis_client, category)
            except Exception as exc:
                logger.warning("Cache promotion failed for %s: %s", category, exc)

    def _refresh_all():
        """Fetch fresh articles per category, AI-curate, write to Redis.

        After all category feeds are refreshed, rebuilds the pre-computed article
        embeddings used by topic-news search. This ensures the embedding store
        stays in sync with the latest articles without hitting RSS feeds a second
        time on the hot path.
        """
        from backend.api.news.cache import fetch_and_cache, refresh_article_embeddings

        for category in NEWS_FEEDS:
            try:
                fetch_and_cache(redis_client, category)
                logger.info("Refreshed news cache for category=%s", category)
            except Exception as exc:
                logger.warning("Cache refresh failed for %s: %s", category, exc)

        # Rebuild article embeddings for topic-news semantic search.
        try:
            count = refresh_article_embeddings(redis_client)
            logger.info("Article embeddings refreshed: %d articles stored", count)
        except Exception as exc:
            logger.warning("Article embedding refresh failed: %s", exc)

    _scheduler.add_job(_promote_all, "interval", hours=1, id="news_cache_promote")
    _scheduler.add_job(
        _refresh_all, "interval", hours=1, minutes=30,
        id="news_cache_refresh", jitter=300,
    )
    _scheduler.start()
    logger.info("News cache scheduler started (promote + refresh + embed jobs)")
    return _scheduler


def get_scheduler() -> BackgroundScheduler:
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialised — call init_scheduler() first")
    return _scheduler
