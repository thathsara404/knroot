from __future__ import annotations

import hashlib
import html as _html
import json
import logging
import re as _re
from datetime import datetime, timezone

import feedparser

from backend.api.news.feeds import ALL_FEEDS, NEWS_FEEDS, ITEMS_PER_FEED

logger = logging.getLogger(__name__)

_DAY_TTL = 86400    # 24 h
_HOUR_TTL = 3600    # 1 h


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode entities from RSS summary text."""
    text = _html.unescape(text)
    text = _re.sub(r'<[^>]+>', ' ', text)
    text = _re.sub(r'\s+', ' ', text).strip()
    return text


def _article_id(link: str) -> str:
    return hashlib.sha256(link.encode()).hexdigest()[:12]


def _parse_published(entry) -> str:
    for attr in ('published', 'updated', 'created'):
        val = entry.get(attr)
        if val:
            return str(val)
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _age_hours(published_str: str) -> float:
    """Return age of an article in hours; returns 0 on parse failure (treat as fresh)."""
    if not published_str:
        return 0.0
    for parser in (
        lambda s: datetime.fromisoformat(s.replace('Z', '+00:00')),
        lambda s: __import__('email.utils', fromlist=['parsedate_to_datetime']).parsedate_to_datetime(s),
    ):
        try:
            dt = parser(published_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        except Exception:
            pass
    return 0.0


def _parse_entry(source: str, entry) -> dict:
    summary = _strip_html((entry.get("summary") or "").strip())
    if len(summary) > 500:
        summary = summary[:500].rsplit(" ", 1)[0] + "..."
    link = (entry.get("link") or "").strip()
    published = _parse_published(entry)
    return {
        "id": _article_id(link) if link else hashlib.sha256(str(entry).encode()).hexdigest()[:12],
        "source": source,
        "title": _strip_html((entry.get("title") or "").strip()),
        "link": link,
        "summary": summary,
        "published": published,
        "_age_hours": _age_hours(published),
    }


def _day_key(category: str, dt: datetime) -> str:
    return f"news:day:{dt.strftime('%Y-%m-%d')}:{category}"


def _hour_key(category: str, dt: datetime) -> str:
    return f"news:hour:{dt.strftime('%Y-%m-%d-%H')}:{category}"


def _fetch_from_feeds(category: str, max_age_hours: float = 24) -> list[dict]:
    feeds = NEWS_FEEDS.get(category, [])
    items: list[dict] = []
    for source, url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:ITEMS_PER_FEED]:
                article = _parse_entry(source, entry)
                if article["_age_hours"] <= max_age_hours:
                    items.append(article)
        except Exception as exc:
            logger.warning("Feed fetch failed [%s] %s: %s", category, url, exc)
    # If strict 24h window yields nothing, relax to 7 days
    if not items and max_age_hours <= 24:
        return _fetch_from_feeds(category, max_age_hours=168)
    return items


def _extract_keywords(topic: str) -> list[str]:
    """Extract search keywords from a topic string.

    Keeps 3+-char words AND 2+-char all-uppercase acronyms (AI, ML, RL, IoT…).
    Deduplicates while preserving order.
    """
    seen: set[str] = set()
    keywords: list[str] = []
    for w in _re.split(r'\W+', topic):
        if not w:
            continue
        # All-uppercase acronyms (≥2 chars) or regular words (≥3 chars)
        if (w.isupper() and len(w) >= 2) or len(w) >= 3:
            kw = w.lower()
            if kw not in seen:
                keywords.append(kw)
                seen.add(kw)
    return keywords


def fetch_topic_news(topic: str, max_age_hours: float = 168) -> list[dict]:
    """Fetch from ALL_FEEDS and return articles relevant to topic.

    Scoring: title match = 2 pts, summary match = 1 pt.
    Falls back to a 30-day window if the requested window yields nothing.
    """
    keywords = _extract_keywords(topic)
    if not keywords:
        return []

    # Collect up to 30 days of articles so we can relax the window if needed
    MAX_COLLECT_AGE = 720
    all_items: list[dict] = []
    seen_ids: set[str] = set()

    for source, url in ALL_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:ITEMS_PER_FEED]:
                article = _parse_entry(source, entry)
                if article["id"] in seen_ids or article["_age_hours"] > MAX_COLLECT_AGE:
                    continue
                seen_ids.add(article["id"])
                all_items.append(article)
        except Exception as exc:
            logger.warning("Topic feed fetch failed %s: %s", url, exc)

    # Score: title hits worth 2×, summary hits worth 1×
    scored: list[tuple[int, dict]] = []
    for article in all_items:
        title_lower = article["title"].lower()
        summary_lower = article.get("summary", "").lower()
        score = (
            sum(2 for kw in keywords if kw in title_lower) +
            sum(1 for kw in keywords if kw in summary_lower)
        )
        scored.append((score, article))
    scored.sort(key=lambda x: -x[0])

    # First try: within the requested window
    recent = [a for s, a in scored if s > 0 and a["_age_hours"] <= max_age_hours][:15]
    if recent:
        return recent

    # Fallback: relax to 30 days before giving up
    return [a for s, a in scored if s > 0 and a["_age_hours"] <= MAX_COLLECT_AGE][:15]


def get_cached(redis_client, category: str) -> list[dict] | None:
    now = datetime.now(timezone.utc)
    for key in (_hour_key(category, now), _day_key(category, now)):
        raw = redis_client.get(key)
        if raw:
            return json.loads(raw)
    return None


def set_cache(redis_client, category: str, articles: list[dict]) -> None:
    now = datetime.now(timezone.utc)
    clean = [{k: v for k, v in a.items() if k != '_age_hours'} for a in articles]
    payload = json.dumps(clean)
    redis_client.setex(_hour_key(category, now), _HOUR_TTL, payload)
    redis_client.setex(_day_key(category, now), _DAY_TTL, payload)


def curate_with_ai(redis_client, category: str, articles: list[dict]) -> list[dict]:
    """Use LLM to rank/filter articles by importance. Falls back to original order on error."""
    if not articles:
        return articles
    try:
        from backend.agent.prompts import NEWS_CURATION_PROMPT
        from backend.core.llm import build_llm_client

        n_select = min(len(articles), 10)
        article_list = "\n".join(
            f"{i}: {a.get('title', '')} — {a.get('source', '')}"
            for i, a in enumerate(articles)
        )
        prompt = NEWS_CURATION_PROMPT.format(
            n_select=n_select,
            article_list=article_list,
        )
        llm = build_llm_client(temperature=0.2)
        resp = llm.invoke(prompt)
        text = str(resp.content).strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(text)
        indices = data.get("selected_indices", [])
        curated = [articles[i] for i in indices if 0 <= i < len(articles)]
        # Append any articles not selected (so we don't lose them)
        selected_set = set(indices)
        rest = [a for i, a in enumerate(articles) if i not in selected_set]
        result = curated + rest
        logger.info(
            "AI curation for %s: selected %d/%d articles",
            category, len(curated), len(articles),
        )
        return result
    except Exception as exc:
        logger.warning("AI curation failed for %s: %s", category, exc)
        return articles


def fetch_and_cache(redis_client, category: str) -> list[dict]:
    articles = _fetch_from_feeds(category)
    if articles:
        articles = curate_with_ai(redis_client, category, articles)
        set_cache(redis_client, category, articles)
    return articles


def promote_hour_to_day(redis_client, category: str) -> None:
    """Promote current hour cache to day cache (called by hourly scheduler job)."""
    now = datetime.now(timezone.utc)
    hour_raw = redis_client.get(_hour_key(category, now))
    if hour_raw:
        redis_client.setex(_day_key(category, now), _DAY_TTL, hour_raw)
        logger.info("Promoted hour→day cache for category=%s", category)
