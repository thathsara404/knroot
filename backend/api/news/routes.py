from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from backend.api.news.feeds import NEWS_FEEDS
from backend.api.news.service import get_news
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
