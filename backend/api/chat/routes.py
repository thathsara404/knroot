from __future__ import annotations

import json

from flask import Blueprint, g, jsonify, make_response, render_template, request

from backend.api.chat.service import auto_title_session, get_or_create_session, send_message
from backend.core.auth import require_api_auth
from backend.core.errors import UnprocessableError

bp = Blueprint("chat", __name__)


def _req_data() -> dict:
    """Read request body from JSON or HTMX form-encoded data."""
    json_data = request.get_json(silent=True)
    if json_data is not None:
        return json_data
    return dict(request.values)


@bp.post("/chat")
@require_api_auth
def chat():
    data = _req_data()
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        raise UnprocessableError("message field is required")

    session_id = get_or_create_session(g.user_id, data.get("session_id") or None)
    result = send_message(g.user_id, session_id, user_msg)

    if result["is_new_conversation"]:
        title_text = (
            result["response"]
            if result.get("response_type") != "sectioned"
            else (
                result["response"].get("intro", "")
                if isinstance(result["response"], dict)
                else ""
            )
        )
        auto_title_session(session_id, user_msg, str(title_text))

    # HTMX: return user bubble + AI response together so beforeend appends both.
    if request.headers.get("HX-Request"):
        user_html = render_template("partials/message.html", role="user", content=user_msg)
        if result.get("response_type") == "sectioned":
            ai_html = render_template(
                "partials/sectioned_message.html",
                data=result["response"],
                session_id=session_id,
            )
        else:
            ai_html = render_template(
                "partials/message.html",
                role="assistant",
                content=result["response"],
            )
        resp = make_response(user_html + ai_html, 200)
        resp.headers["HX-Session-Id"] = session_id
        return resp

    return jsonify(result)


@bp.post("/chat/quiz-section")
@require_api_auth
def quiz_section():
    data = _req_data()
    session_id = data.get("session_id")
    section_id = data.get("section_id")
    section_content = data.get("section_content", "")
    if not section_id or not section_content:
        raise UnprocessableError("section_id and section_content required")

    # Generate MCQs using LLM
    from backend.agent.prompts import MCQ_GENERATION_PROMPT
    from backend.core.llm import build_llm_client

    llm = build_llm_client(temperature=0.5)
    prompt = MCQ_GENERATION_PROMPT.replace(
        "{conversation_text}", section_content,
    ).replace(
        "exactly 8 multiple-choice", "3-5 multiple-choice",
    )

    questions = []
    try:
        resp = llm.invoke(prompt)
        text = str(resp.content).strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        questions = parsed.get("questions", [])[:5]
    except Exception:
        questions = []

    return render_template(
        "partials/quiz_section.html",
        questions=questions,
        section_id=section_id,
        session_id=session_id,
    )
