from flask import Blueprint, jsonify, request

from backend.api.news.feeds import NEWS_FEEDS
from backend.api.news.service import get_news
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
