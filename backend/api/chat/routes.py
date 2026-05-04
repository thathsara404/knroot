from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from backend.api.chat.service import auto_title_session, get_or_create_session, send_message
from backend.core.auth import require_auth
from backend.core.errors import UnprocessableError

bp = Blueprint("chat", __name__)


@bp.post("/chat")
@require_auth
def chat():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        raise UnprocessableError("message field is required")

    session_id = get_or_create_session(g.user_id, data.get("session_id"))
    result = send_message(g.user_id, session_id, user_msg)

    if result["is_new_conversation"]:
        auto_title_session(session_id, user_msg, result["response"])

    return jsonify(result)
