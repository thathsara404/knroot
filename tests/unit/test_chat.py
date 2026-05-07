"""Unit tests for chat routes."""
import pytest

CHAT_SVC = "backend.api.chat.service"
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
    mocker.patch(f"{CHAT_SVC}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_SVC}.send_message", return_value=_PLAIN)
    mocker.patch(f"{CHAT_SVC}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Hello", "session_id": "sess-1"})
    assert resp.status_code == 200


def test_chat_htmx_returns_session_id_header(authed_client, mocker):
    mocker.patch(f"{CHAT_SVC}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_SVC}.send_message", return_value=_PLAIN)
    mocker.patch(f"{CHAT_SVC}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Hi"}, headers=HTMX)
    assert resp.status_code == 200
    assert resp.headers.get("HX-Session-Id") == "sess-1"


def test_chat_htmx_contains_response_text(authed_client, mocker):
    mocker.patch(f"{CHAT_SVC}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_SVC}.send_message", return_value=_PLAIN)
    mocker.patch(f"{CHAT_SVC}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Hi"}, headers=HTMX)
    assert b"Hello, world!" in resp.data


# ── sectioned response ────────────────────────────────────────────────────────

def test_chat_htmx_sectioned_renders_section_title(authed_client, mocker):
    mocker.patch(f"{CHAT_SVC}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_SVC}.send_message", return_value=_SECTIONED)
    mocker.patch(f"{CHAT_SVC}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Explain it"}, headers=HTMX)
    assert resp.status_code == 200
    assert b"Gradient Descent" in resp.data


def test_chat_new_conversation_calls_auto_title(authed_client, mocker):
    mocker.patch(f"{CHAT_SVC}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_SVC}.send_message", return_value={**_PLAIN, "is_new_conversation": True})
    title_mock = mocker.patch(f"{CHAT_SVC}.auto_title_session")
    authed_client.post("/chat", json={"message": "Hi"})
    title_mock.assert_called_once()


def test_chat_existing_session_skips_auto_title(authed_client, mocker):
    mocker.patch(f"{CHAT_SVC}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_SVC}.send_message", return_value={**_PLAIN, "is_new_conversation": False})
    title_mock = mocker.patch(f"{CHAT_SVC}.auto_title_session")
    authed_client.post("/chat", json={"message": "Hi"})
    title_mock.assert_not_called()
