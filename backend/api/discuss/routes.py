from __future__ import annotations

from flask import Blueprint, g, jsonify, make_response, render_template, request

from backend.api.discuss import service as discuss_svc
from backend.core.auth import require_api_auth
from backend.core.errors import UnprocessableError

bp = Blueprint("discuss", __name__)


def _req_data() -> dict:
    json_data = request.get_json(silent=True)
    if json_data is not None:
        return json_data
    return dict(request.values)


@bp.post("/news/discuss")
@require_api_auth
def news_discuss():
    data = _req_data()
    required = ("article_id", "article_title", "article_link")
    missing = [f for f in required if not data.get(f)]
    if missing:
        raise UnprocessableError(f"Missing fields: {', '.join(missing)}")

    result = discuss_svc.news_discuss(
        user_id=g.user_id,
        article_id=data["article_id"],
        article_title=data["article_title"],
        article_summary=data.get("article_summary", ""),
        article_link=data["article_link"],
        source_category=data.get("source_category") or None,
    )

    # HTMX: render the first AI response directly into #chat-messages.
    if request.headers.get("HX-Request"):
        first = result["first_response"]
        if isinstance(first, dict) and first.get("type") == "sectioned":
            html = render_template(
                "partials/sectioned_message.html",
                data=first,
                session_id=result["session_id"],
                article_link=data.get("article_link", ""),
                article_title=data.get("article_title", ""),
            )
        else:
            text = first.get("text", str(first)) if isinstance(first, dict) else str(first)
            html = render_template("partials/message.html", role="assistant", content=text)
        resp = make_response(html, 200)
        resp.headers["HX-Session-Id"] = result["session_id"]
        return resp

    return jsonify(result), 201


@bp.post("/sessions/<session_id>/learn-more")
@require_api_auth
def learn_more(session_id: str):
    data = _req_data()
    topic = (data.get("topic") or "").strip()
    if not topic:
        raise UnprocessableError("topic is required")

    result = discuss_svc.create_learn_more(g.user_id, session_id, topic)
    return jsonify(result), 201
