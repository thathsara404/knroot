from __future__ import annotations

from flask import Blueprint, g, jsonify, render_template, request

from backend.api.sessions import service as sessions_svc
from backend.core.auth import require_api_auth, require_auth
from backend.core.errors import UnprocessableError

bp = Blueprint("sessions", __name__)


@bp.post("/sessions")
@require_api_auth
def create_session():
    data = request.get_json(silent=True) or {}
    session = sessions_svc.create_session(
        user_id=g.user_id,
        session_type=data.get("session_type", "regular"),
        parent_session_id=data.get("parent_session_id"),
        topic=data.get("topic"),
        news_article_id=data.get("news_article_id"),
        title=data.get("title"),
    )
    return jsonify(session), 201


@bp.get("/sessions")
@require_api_auth
def list_sessions():
    return jsonify(sessions_svc.list_sessions(g.user_id))


@bp.get("/sessions/partial")
@require_auth
def session_list_partial():
    sessions = sessions_svc.list_sessions(g.user_id)
    expand_id = request.args.get('expand', '')
    return render_template("partials/session_list.html", sessions=sessions, expand_id=expand_id)


@bp.patch("/sessions/<session_id>")
@require_api_auth
def rename_session(session_id: str):
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        raise UnprocessableError("title is required")
    sessions_svc.rename_session(g.user_id, session_id, title)
    return "", 204


@bp.delete("/sessions/<session_id>")
@require_api_auth
def delete_session(session_id: str):
    sessions_svc.delete_session(g.user_id, session_id)
    return "", 204


@bp.post("/sessions/<session_id>/regenerate")
@require_api_auth
def regenerate_session(session_id: str):
    result = sessions_svc.regenerate_session(g.user_id, session_id)
    return jsonify(result)


@bp.get("/sessions/<session_id>/messages")
@require_api_auth
def get_messages(session_id: str):
    return jsonify(sessions_svc.get_messages(g.user_id, session_id))


@bp.get("/sessions/<session_id>/messages/partial")
@require_auth
def messages_partial(session_id: str):
    session = sessions_svc.get_session(g.user_id, session_id)

    # Quiz sessions have no session_messages — render quiz inline directly
    if session and session.get("session_type") == "quiz":
        attempt_id = session.get("linked_attempt_id")
        if attempt_id:
            from backend.api.quiz.service import get_attempt
            attempt = get_attempt(g.user_id, str(attempt_id))
            return render_template(
                "partials/quiz_inline.html",
                attempt=attempt,
                session_title=session.get("title") or "Knowledge Check",
                quiz_session_id=session_id,  # quiz session IS the current session
            )

    messages = sessions_svc.get_messages(g.user_id, session_id)
    article_link = ""
    article_title = ""
    if session and session.get("session_type") == "news_discussion":
        article_link = session.get("topic") or ""
        article_title = session.get("title") or ""
    return render_template(
        "partials/messages.html",
        messages=messages,
        session=session,
        article_link=article_link,
        article_title=article_title,
    )


@bp.get("/sessions/<session_id>/tree")
@require_api_auth
def get_tree(session_id: str):
    return jsonify(sessions_svc.get_tree(g.user_id, session_id))


@bp.get("/sessions/<session_id>/tree/partial")
@require_auth
def tree_partial(session_id: str):
    tree = sessions_svc.get_tree(g.user_id, session_id)
    return render_template("partials/knowledge_tree.html", tree=tree, session_id=session_id)


@bp.get("/sessions/<session_id>/knowledge-tree/partial")
@require_auth
def knowledge_tree_panel(session_id: str):
    tree = sessions_svc.get_knowledge_tree(g.user_id, session_id)
    return render_template(
        "partials/knowledge_tree_panel.html",
        tree=tree,
        active_session_id=session_id,
    )
