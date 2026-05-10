"""Unit tests for chat routes."""
import pytest

# Routes import these names directly, so mocks must target the routes namespace.
CHAT_ROUTES = "backend.api.chat.routes"
HTMX = {"HX-Request": "true"}

_PLAIN = {
    "response": "Hello, world!",
    "response_type": "plain",
    "session_id": "sess-1",
    "is_new_conversation": False,
    "suggested_topics": [],
}

_SECTIONED = {
    "response": {
        "type": "sectioned",
        "intro": "Overview text",
        "sections": [
            {"id": "s1", "title": "Gradient Descent", "content": "Optimization method.", "learn_more_topic": "Gradient Descent"}
        ],
        "outro": "Summary line.",
    },
    "response_type": "sectioned",
    "session_id": "sess-1",
    "is_new_conversation": True,
    "suggested_topics": ["Backprop", "Adam optimizer"],
}


# ── auth ──────────────────────────────────────────────────────────────────────

def test_chat_requires_auth(client):
    assert client.post("/chat", json={"message": "hello"}).status_code == 401


def test_quiz_section_requires_auth(client):
    assert client.post("/chat/quiz-section", json={"section_id": "s1", "section_content": "x"}).status_code == 401


# ── validation ────────────────────────────────────────────────────────────────

def test_chat_missing_message_returns_422(authed_client):
    resp = authed_client.post("/chat", json={})
    assert resp.status_code == 422


def test_chat_empty_message_returns_422(authed_client):
    resp = authed_client.post("/chat", json={"message": "   "})
    assert resp.status_code == 422


def test_quiz_section_missing_section_id_returns_422(authed_client):
    resp = authed_client.post("/chat/quiz-section", json={"section_content": "something long enough"})
    assert resp.status_code == 422


def test_quiz_section_missing_content_returns_422(authed_client):
    resp = authed_client.post("/chat/quiz-section", json={"section_id": "s1"})
    assert resp.status_code == 422


# ── plain response ────────────────────────────────────────────────────────────

def test_chat_returns_200_json(authed_client, mocker):
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value=_PLAIN)
    mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Hello", "session_id": "sess-1"})
    assert resp.status_code == 200


def test_chat_htmx_returns_session_id_header(authed_client, mocker):
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value=_PLAIN)
    mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Hi"}, headers=HTMX)
    assert resp.status_code == 200
    assert resp.headers.get("HX-Session-Id") == "sess-1"


def test_chat_htmx_contains_response_text(authed_client, mocker):
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value=_PLAIN)
    mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Hi"}, headers=HTMX)
    assert b"Hello, world!" in resp.data


# ── sectioned response ────────────────────────────────────────────────────────

def test_chat_htmx_sectioned_renders_section_title(authed_client, mocker):
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value=_SECTIONED)
    mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Explain it"}, headers=HTMX)
    assert resp.status_code == 200
    assert b"Gradient Descent" in resp.data


def test_chat_new_conversation_calls_auto_title(authed_client, mocker):
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value={**_PLAIN, "is_new_conversation": True})
    title_mock = mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    authed_client.post("/chat", json={"message": "Hi"})
    title_mock.assert_called_once()


def test_chat_existing_session_skips_auto_title(authed_client, mocker):
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value={**_PLAIN, "is_new_conversation": False})
    title_mock = mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    authed_client.post("/chat", json={"message": "Hi"})
    title_mock.assert_not_called()


# ── _parse_llm_response — pure function ──────────────────────────────────────

import json as _json
from backend.api.chat.service import _parse_llm_response


def test_parse_plain_text_returns_plain():
    val, typ = _parse_llm_response("Hello world")
    assert typ == "plain"
    assert val == "Hello world"


def test_parse_whitespace_only_is_plain():
    val, typ = _parse_llm_response("   ")
    assert typ == "plain"


def test_parse_valid_sectioned_json():
    data = {"type": "sectioned", "sections": [{"id": "s1", "title": "T", "content": "C"}]}
    val, typ = _parse_llm_response(_json.dumps(data))
    assert typ == "sectioned"
    assert val == data


def test_parse_plain_type_json_extracts_text():
    data = {"type": "plain", "text": "Extracted text"}
    val, typ = _parse_llm_response(_json.dumps(data))
    assert typ == "plain"
    assert val == "Extracted text"


def test_parse_strips_markdown_fences_before_parsing():
    data = {"type": "sectioned", "sections": [{"id": "s1", "title": "T", "content": "C"}]}
    fenced = f"```json\n{_json.dumps(data)}\n```"
    val, typ = _parse_llm_response(fenced)
    assert typ == "sectioned"
    assert val == data


def test_parse_invalid_json_returns_plain():
    val, typ = _parse_llm_response("{not valid json at all}")
    assert typ == "plain"
    assert "{not valid json at all}" == val


def test_parse_unknown_type_json_returns_plain():
    val, typ = _parse_llm_response(_json.dumps({"type": "unknown", "data": "x"}))
    assert typ == "plain"


def test_parse_non_dict_json_array_returns_plain():
    val, typ = _parse_llm_response(_json.dumps([1, 2, 3]))
    assert typ == "plain"


def test_parse_sectioned_missing_sections_key_returns_plain():
    val, typ = _parse_llm_response(_json.dumps({"type": "sectioned"}))
    assert typ == "plain"


def test_parse_plain_type_missing_text_key_returns_plain():
    val, typ = _parse_llm_response(_json.dumps({"type": "plain"}))
    assert typ == "plain"


def test_parse_fenced_without_language_tag_still_works():
    data = {"type": "sectioned", "sections": [{"id": "s1", "title": "T", "content": "C"}]}
    fenced = f"```\n{_json.dumps(data)}\n```"
    val, typ = _parse_llm_response(fenced)
    assert typ == "sectioned"
