from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import feedparser

from backend.api.news.feeds import NEWS_FEEDS, ITEMS_PER_FEED

logger = logging.getLogger(__name__)

_DAY_TTL = 86400    # 24 h
_HOUR_TTL = 3600    # 1 h


def _day_key(category: str, dt: datetime) -> str:
    return f"news:day:{dt.strftime('%Y-%m-%d')}:{category}"


def _hour_key(category: str, dt: datetime) -> str:
    return f"news:hour:{dt.strftime('%Y-%m-%d-%H')}:{category}"


def _fetch_from_feeds(category: str) -> list[dict]:
    feeds = NEWS_FEEDS.get(category, [])
    items: list[dict] = []
    for source, url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:ITEMS_PER_FEED]:
                summary = (entry.get("summary") or "").strip()
                if len(summary) > 200:
                    summary = summary[:200].rsplit(" ", 1)[0] + "..."
                items.append({
                    "source": source,
                    "title": (entry.get("title") or "").strip(),
                    "link": (entry.get("link") or "").strip(),
                    "summary": summary,
                })
        except Exception as exc:
            logger.warning("Feed fetch failed [%s] %s: %s", category, url, exc)
    return items


def get_cached(redis_client, category: str) -> list[dict] | None:
    now = datetime.now(timezone.utc)
    for key in (_hour_key(category, now), _day_key(category, now)):
        raw = redis_client.get(key)
        if raw:
            return json.loads(raw)
    return None


def set_cache(redis_client, category: str, articles: list[dict]) -> None:
    now = datetime.now(timezone.utc)
    payload = json.dumps(articles)
    redis_client.setex(_hour_key(category, now), _HOUR_TTL, payload)
    redis_client.setex(_day_key(category, now), _DAY_TTL, payload)


def fetch_and_cache(redis_client, category: str) -> list[dict]:
    articles = _fetch_from_feeds(category)
    if articles:
        set_cache(redis_client, category, articles)
    return articles


def promote_hour_to_day(redis_client, category: str) -> None:
    """Promote current hour cache to day cache (called by hourly scheduler job)."""
    now = datetime.now(timezone.utc)
    hour_raw = redis_client.get(_hour_key(category, now))
    if hour_raw:
        redis_client.setex(_day_key(category, now), _DAY_TTL, hour_raw)
        logger.info("Promoted hour→day cache for category=%s", category)
