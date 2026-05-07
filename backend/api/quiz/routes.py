from __future__ import annotations

from flask import Blueprint, g, jsonify, render_template, request

from backend.api.quiz import service as quiz_svc
from backend.core.auth import require_api_auth, require_auth
from backend.core.db import query_one
from backend.core.errors import UnprocessableError

bp = Blueprint("quiz", __name__)


def _data() -> dict:
    d = request.get_json(silent=True)
    return d if d is not None else dict(request.values)


@bp.post("/quiz/generate")
@require_api_auth
def generate():
    data = _data()
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        raise UnprocessableError("session_id is required")
    section_content = (data.get("section_content") or "").strip() or None
    section_title = (data.get("section_title") or "").strip() or None
    result = quiz_svc.generate_quiz(
        g.user_id, session_id,
        section_content=section_content,
        section_title=section_title,
    )
    return jsonify(result)


@bp.post("/quiz/generate-followup")
@require_api_auth
def generate_followup():
    data = _data()
    attempt_id = (data.get("attempt_id") or "").strip()
    if not attempt_id:
        raise UnprocessableError("attempt_id is required")
    result = quiz_svc.generate_quiz_followup(g.user_id, attempt_id)
    return jsonify(result)


@bp.get("/quiz/<attempt_id>/partial")
@require_auth
def quiz_inline_partial(attempt_id: str):
    attempt = quiz_svc.get_attempt(g.user_id, attempt_id)
    row = query_one("SELECT title FROM chat_sessions WHERE id = %s", (attempt["session_id"],))
    session_title = row["title"] if row else "Knowledge Check"
    quiz_row = query_one(
        "SELECT id FROM chat_sessions WHERE linked_attempt_id = %s AND user_id = %s",
        (attempt_id, g.user_id),
    )
    quiz_session_id = str(quiz_row["id"]) if quiz_row else ""
    return render_template(
        "partials/quiz_inline.html",
        attempt=attempt,
        session_title=session_title,
        quiz_session_id=quiz_session_id,
    )


@bp.get("/quiz/attempt/<attempt_id>")
@require_api_auth
def get_attempt(attempt_id: str):
    return jsonify(quiz_svc.get_attempt(g.user_id, attempt_id))


@bp.put("/quiz/attempt/<attempt_id>")
@require_api_auth
def save_answers(attempt_id: str):
    data = _data()
    answers = data.get("answers") or {}
    submit = bool(data.get("completed") or data.get("submit"))
    result = quiz_svc.save_answers(g.user_id, attempt_id, answers, submit=submit)
    return jsonify(result)


@bp.post("/quiz/retry")
@require_api_auth
def retry():
    data = _data()
    attempt_id = (data.get("attempt_id") or "").strip()
    if not attempt_id:
        raise UnprocessableError("attempt_id is required")
    result = quiz_svc.retry_quiz(g.user_id, attempt_id)
    return jsonify(result)


@bp.get("/quiz/attempts")
@require_api_auth
def list_attempts():
    session_id = request.args.get("session_id", "").strip()
    if not session_id:
        raise UnprocessableError("session_id query param is required")
    return jsonify(quiz_svc.list_attempts(g.user_id, session_id))


@bp.get("/quiz/attempt/<attempt_id>/relearn/<question_id>")
@require_api_auth
def get_relearn(attempt_id: str, question_id: str):
    return jsonify(quiz_svc.get_relearn(g.user_id, attempt_id, question_id))
