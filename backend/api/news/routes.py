from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, render_template, request

logger = logging.getLogger(__name__)

from backend.api.news.feeds import NEWS_FEEDS
from backend.api.news.service import get_news, get_topic_news
from backend.core.auth import require_api_auth, require_auth
from backend.core.errors import UnprocessableError

bp = Blueprint("news", __name__)


@bp.get("/news")
def news():
    category = request.args.get("category", "ai").lower()
    if category not in NEWS_FEEDS:
        raise UnprocessableError(f"Unknown category. Valid: {list(NEWS_FEEDS)}")
    force = request.args.get("force", "false").lower() == "true"
    articles = get_news(category, force=force)
    return jsonify({"category": category, "articles": articles})


@bp.get("/news/partial")
@require_auth
def news_partial():
    category = request.args.get("category", "ai").lower()
    if category not in NEWS_FEEDS:
        category = "ai"
    articles = get_news(category, force=False)
    return render_template(
        "partials/news_panel.html",
        articles=articles,
        category=category,
    )


@bp.get("/news/topic-partial")
@require_auth
def topic_news_partial():
    topic = request.args.get("topic", "").strip()
    session_id = request.args.get("session_id", "").strip()
    hours = min(int(request.args.get("hours", 168)), 720)
    force = request.args.get("force", "false").lower() == "true"

    # Resolve topic from session if not supplied directly
    if session_id and not topic:
        from backend.api.sessions.service import get_session
        session = get_session(g.user_id, session_id)
        if session:
            stype = session.get("session_type", "")
            if stype == "news_discussion":
                # topic stores the article URL — use the article title instead
                topic = session.get("title") or ""
            elif stype == "quiz":
                raw = session.get("topic") or session.get("title") or ""
                topic = raw if raw.lower() not in ("quiz", "") else ""
            else:
                topic = session.get("topic") or session.get("title") or ""

    try:
        articles = get_topic_news(topic, hours, force=force) if topic else get_news("ai", force=force)
    except Exception:
        logger.exception("topic-partial failed, falling back to general news")
        articles = get_news("ai")
        topic = ""
    return render_template(
        "partials/topic_news_panel.html",
        articles=articles,
        topic=topic,
        hours=hours,
        session_id=session_id,
    )


@bp.post("/news/fact-check")
@require_api_auth
def news_fact_check():
    from backend.agent.pipeline import run_fact_check

    # Support both JSON and HTMX form data
    json_data = request.get_json(silent=True)
    if json_data is not None:
        data = json_data
    else:
        data = dict(request.values)

    article_title = (data.get("article_title") or "").strip()
    article_summary = (data.get("article_summary") or "").strip()
    article_link = (data.get("article_link") or "").strip()

    if not article_title:
        raise UnprocessableError("article_title is required")

    report = run_fact_check(article_title, article_summary, article_link)

    if request.headers.get("HX-Request"):
        return render_template(
            "partials/fact_check_report.html",
            report=report,
            article_title=article_title,
        )
    return jsonify(report)
