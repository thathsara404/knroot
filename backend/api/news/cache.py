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


# ── Article parsing helpers ───────────────────────────────────────────────────

def _strip_html(text: str) -> str:
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
    return ""  # no date in feed — never fabricate ingestion time as published


def _parse_dt(published_str: str) -> datetime | None:
    """Parse any RSS date string to a timezone-aware datetime, or None on failure."""
    for parser in (
        lambda s: datetime.fromisoformat(s.replace('Z', '+00:00')),
        lambda s: __import__('email.utils', fromlist=['parsedate_to_datetime']).parsedate_to_datetime(s),
    ):
        try:
            dt = parser(published_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return None


def _age_hours(published_str: str) -> float:
    """Return age of an article in hours; returns 0 on parse failure (treat as fresh)."""
    if not published_str:
        return 0.0
    dt = _parse_dt(published_str)
    if dt:
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    return 0.0


def _parse_entry(source: str, entry) -> dict:
    summary = _strip_html((entry.get("summary") or "").strip())
    if len(summary) > 500:
        summary = summary[:500].rsplit(" ", 1)[0] + "..."
    link = (entry.get("link") or "").strip()
    published_raw = _parse_published(entry)
    dt = _parse_dt(published_raw)
    published_iso = dt.isoformat() if dt else published_raw
    return {
        "id": _article_id(link) if link else hashlib.sha256(str(entry).encode()).hexdigest()[:12],
        "source": source,
        "title": _strip_html((entry.get("title") or "").strip()),
        "link": link,
        "summary": summary,
        "published": published_iso,
        "_age_hours": _age_hours(published_raw),
    }


# ── Category news cache (day/hour keys) ──────────────────────────────────────

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
    if not items and max_age_hours <= 24:
        return _fetch_from_feeds(category, max_age_hours=168)
    items.sort(key=lambda a: a["_age_hours"])  # newest first before curation
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

        # Pick at most 5 top stories, capped at half the total so there is always
        # a meaningful non-curated remainder for the "newest first" tail.
        n_select = min(len(articles) // 2, 5)
        if n_select < 1:
            return articles
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
        indices = [i for i in data.get("selected_indices", []) if 0 <= i < len(articles)][:n_select]
        selected_set = set(indices)
        curated = [{**articles[i], "_curated": True} for i in indices]
        rest = sorted(
            (articles[i] for i in range(len(articles)) if i not in selected_set),
            key=lambda a: a.get("_age_hours", 0),
        )
        result = curated + rest
        logger.info("AI curation for %s: selected %d/%d articles", category, len(curated), len(articles))
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


# ── Topic news — embedding-based search ──────────────────────────────────────

# Maximum article age to collect for topic scoring (30 days).
_MAX_COLLECT_AGE = 720


def _collect_all_articles() -> list[dict]:
    """Fetch the most recent articles from every feed in ALL_FEEDS.

    Dedupes by article id. Collects up to 30 days old so the topic ranker
    has a large candidate pool even for less-covered topics.
    """
    items: list[dict] = []
    seen_ids: set[str] = set()
    for source, url in ALL_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:ITEMS_PER_FEED]:
                article = _parse_entry(source, entry)
                if article["id"] in seen_ids or article["_age_hours"] > _MAX_COLLECT_AGE:
                    continue
                seen_ids.add(article["id"])
                items.append(article)
        except Exception as exc:
            logger.warning("Topic feed fetch failed %s: %s", url, exc)
    return items


def refresh_article_embeddings(redis_client) -> int:
    """Fetch all feeds, compute per-article title + summary embeddings, store in Redis.

    Called by the APScheduler refresh job so that topic-news queries always
    have fresh pre-computed embeddings available without touching the RSS feeds
    on the hot path.

    Redis key:  news:article_embeddings:{MODEL_NAME}:{MODEL_VERSION}
    TTL:        1 hour (matches the scheduler refresh interval)

    Returns the number of articles embedded and stored.
    """
    from backend.api.news.embeddings import embed_articles, ARTICLE_EMBED_KEY, ARTICLE_EMBED_TTL

    articles = _collect_all_articles()
    if not articles:
        logger.warning("refresh_article_embeddings: no articles fetched from any feed")
        return 0

    enriched = embed_articles(articles)
    redis_client.setex(ARTICLE_EMBED_KEY, ARTICLE_EMBED_TTL, json.dumps(enriched))
    logger.info(
        "Stored embeddings for %d articles under key=%s (TTL=%ds)",
        len(enriched), ARTICLE_EMBED_KEY, ARTICLE_EMBED_TTL,
    )
    return len(enriched)


def fetch_topic_news(topic: str, max_age_hours: float = 168, force: bool = False) -> list[dict]:
    """Return articles from ALL_FEEDS ranked by semantic relevance to topic.

    Pipeline (in order):
      1. Load pre-computed article embeddings from Redis (written by scheduler).
         Skipped when force=True — fetches all RSS feeds fresh and re-embeds
         so the user sees any articles published since the last scheduler run.
         Falls back to fresh fetch+embed if the Redis key is missing.
      2. Filter candidates to the requested age window; relax to 30 days if empty.
      3. Re-compute _age_hours from the published timestamp so cached values
         (which were correct at embed time) are not stale at query time.
      4. Embed the topic string (1 vector, ~2 ms).
      5. Weighted cosine similarity:
           score = 0.7 × cos_sim(topic, title) + 0.3 × cos_sim(topic, summary)
         Title is weighted higher because it is the densest signal.
      6. Adaptive threshold = max(0.15, top_score × 0.6).
         Scales with match quality so niche topics still surface results and
         strong topics still filter noise.
      7. Maximal Marginal Relevance re-ranking for diversity.
         Prevents 15 articles from the same source or sub-angle.
      8. On any embedding failure, falls back to keyword scoring (keyword
         matching + proportional min-score threshold).
    """
    from backend.api.news.embeddings import (
        ARTICLE_EMBED_KEY,
        ARTICLE_EMBED_TTL,
        embed,
        embed_articles,
        weighted_scores,
        adaptive_threshold,
        mmr_rerank,
    )
    import numpy as np

    # Step 1 — load pre-computed embeddings from Redis, unless force=True.
    # force=True means the user explicitly requested fresh content — skip the
    # embedding store, re-fetch all RSS feeds, and re-embed so any articles
    # published since the last scheduler run are included.
    articles_with_embs: list[dict] | None = None
    if not force:
        try:
            from backend.extensions import get_redis
            raw = get_redis().get(ARTICLE_EMBED_KEY)
            if raw:
                articles_with_embs = json.loads(raw)
                logger.debug(
                    "fetch_topic_news: loaded %d pre-computed embeddings from Redis",
                    len(articles_with_embs),
                )
        except Exception as exc:
            logger.warning("fetch_topic_news: could not load cached embeddings (%s)", exc)

    if articles_with_embs is None:
        raw_articles = _collect_all_articles()
        if not raw_articles:
            return []
        try:
            articles_with_embs = embed_articles(raw_articles)
            # Write the freshly computed embeddings back to Redis so subsequent
            # topic queries benefit from this fetch without hitting feeds again.
            try:
                from backend.extensions import get_redis
                get_redis().setex(ARTICLE_EMBED_KEY, ARTICLE_EMBED_TTL, json.dumps(articles_with_embs))
                logger.info(
                    "fetch_topic_news: wrote %d fresh embeddings to Redis (force=%s)",
                    len(articles_with_embs), force,
                )
            except Exception as exc:
                logger.warning("fetch_topic_news: could not write embeddings to Redis (%s)", exc)
        except Exception as exc:
            logger.warning("fetch_topic_news: embedding failed, falling back to keywords (%s)", exc)
            return _rank_by_keywords(topic, raw_articles, max_age_hours, _MAX_COLLECT_AGE)

    # Step 2 — re-compute age from published timestamp (cached _age_hours is stale).
    for a in articles_with_embs:
        a["_age_hours"] = _age_hours(a.get("published", ""))

    # Step 3 — filter to requested age window; relax to 30 days if empty.
    candidates = [a for a in articles_with_embs if a["_age_hours"] <= max_age_hours]
    if not candidates:
        candidates = [a for a in articles_with_embs if a["_age_hours"] <= _MAX_COLLECT_AGE]
    if not candidates:
        return []

    try:
        # Step 4 — embed the topic.
        topic_emb = embed([topic])[0]

        # Step 5 — weighted cosine similarity.
        title_embs = np.array([a["title_emb"] for a in candidates])
        summary_embs = np.array([a["summary_emb"] for a in candidates])
        scores = weighted_scores(topic_emb, title_embs, summary_embs).tolist()

        # Step 6 — adaptive threshold.
        threshold = adaptive_threshold(scores)
        filtered = [(s, a) for s, a in zip(scores, candidates) if s >= threshold]
        if not filtered:
            return []

        # Step 7 — MMR re-ranking.
        f_articles = [a for _, a in filtered]
        f_title_embs = np.array([a["title_emb"] for a in f_articles])
        f_summary_embs = np.array([a["summary_emb"] for a in f_articles])
        result = mmr_rerank(topic_emb, f_articles, f_title_embs, f_summary_embs, k=15)

        # Strip embedding vectors — they are internal and must not reach the template.
        return [{k: v for k, v in a.items() if k not in ("title_emb", "summary_emb")} for a in result]

    except Exception as exc:
        logger.warning("fetch_topic_news: ranking failed, falling back to keywords (%s)", exc)
        clean = [{k: v for k, v in a.items() if k not in ("title_emb", "summary_emb")} for a in candidates]
        return _rank_by_keywords(topic, clean, max_age_hours, _MAX_COLLECT_AGE)


# ── Keyword fallback ──────────────────────────────────────────────────────────
# Used when the embedding model is unavailable (missing package, OOM, etc.).

_STOPWORDS = frozenset({
    'the', 'and', 'for', 'with', 'this', 'that', 'from', 'are', 'was', 'has',
    'have', 'had', 'been', 'will', 'can', 'may', 'not', 'but', 'its', 'into',
    'about', 'more', 'also', 'how', 'why', 'what', 'when', 'where', 'which',
    'all', 'our', 'your', 'their', 'his', 'her', 'out', 'off', 'over', 'own',
    'new', 'top', 'best', 'guide', 'overview', 'report', 'review', 'update',
    'using', 'based', 'first', 'just', 'make', 'get', 'use', 'one', 'two',
    'now', 'day', 'year', 'week', 'time', 'way', 'well', 'even', 'each',
    'show', 'shows', 'says', 'said', 'after', 'before', 'during', 'while',
    'between', 'through', 'since', 'than', 'then', 'too', 'very', 'here',
    'latest', 'open', 'next', 'last', 'used', 'like', 'need', 'want', 'make',
    'roadmap', 'announces', 'announced', 'launches', 'launch', 'releases',
})

_YEAR_RE = _re.compile(r'^\d{4}$')


def _extract_keywords(topic: str) -> list[str]:
    seen: set[str] = set()
    keywords: list[str] = []
    for w in _re.split(r'\W+', topic):
        if not w or _YEAR_RE.match(w):
            continue
        is_acronym = w.isupper() and len(w) >= 2
        is_word = len(w) >= 3
        if is_acronym or is_word:
            kw = w.lower()
            if kw not in seen and kw not in _STOPWORDS:
                keywords.append(kw)
                seen.add(kw)
    return keywords


def _rank_by_keywords(
    topic: str,
    articles: list[dict],
    max_age_hours: float,
    max_collect_age: float,
) -> list[dict]:
    keywords = _extract_keywords(topic)
    if not keywords:
        return []
    min_score = max(2, len(keywords) // 3)

    scored: list[tuple[int, dict]] = []
    for article in articles:
        title_lower = article["title"].lower()
        summary_lower = article.get("summary", "").lower()
        score = (
            sum(2 for kw in keywords if kw in title_lower)
            + sum(1 for kw in keywords if kw in summary_lower)
        )
        scored.append((score, article))
    scored.sort(key=lambda x: (-x[0], x[1]["_age_hours"]))

    recent = [a for s, a in scored if s >= min_score and a["_age_hours"] <= max_age_hours][:15]
    if recent:
        return recent
    return [a for s, a in scored if s >= min_score and a["_age_hours"] <= max_collect_age][:15]
