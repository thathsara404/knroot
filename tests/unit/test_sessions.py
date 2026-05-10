"""Unit tests for sessions routes."""
import pytest

SVC = "backend.api.sessions.service"

_SESSION = {
    "id": "sess-uuid-1",
    "user_id": "user-uuid-1234",
    "thread_id": "thread-uuid-1",
    "title": "Test Session",
    "session_type": "regular",
    "parent_session_id": None,
    "root_session_id": None,
    "depth_level": 0,
    "topic": None,
    "news_article_id": None,
    "created_at": "2026-01-01T00:00:00+00:00",
    "last_message_at": "2026-01-01T00:00:00+00:00",
    "child_count": 0,
}

_MSG = {"role": "user", "content": "Hello", "content_type": "plain", "content_data": None}


# ── auth guards ───────────────────────────────────────────────────────────────

def test_list_sessions_requires_auth(client):
    assert client.get("/sessions").status_code == 401


def test_create_session_requires_auth(client):
    assert client.post("/sessions", json={"session_type": "regular"}).status_code == 401


def test_rename_session_requires_auth(client):
    assert client.patch("/sessions/sess-1", json={"title": "X"}).status_code == 401


def test_delete_session_requires_auth(client):
    assert client.delete("/sessions/sess-1").status_code == 401


def test_get_messages_requires_auth(client):
    assert client.get("/sessions/sess-1/messages").status_code == 401


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_sessions_returns_200(authed_client, mocker):
    mocker.patch(f"{SVC}.list_sessions", return_value=[_SESSION])
    resp = authed_client.get("/sessions")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert data[0]["id"] == "sess-uuid-1"


def test_list_sessions_calls_service_with_user_id(authed_client, mocker):
    mock = mocker.patch(f"{SVC}.list_sessions", return_value=[])
    authed_client.get("/sessions")
    mock.assert_called_once_with("user-uuid-1234")


def test_list_sessions_empty(authed_client, mocker):
    mocker.patch(f"{SVC}.list_sessions", return_value=[])
    resp = authed_client.get("/sessions")
    assert resp.status_code == 200
    assert resp.get_json() == []


# ── create ────────────────────────────────────────────────────────────────────

def test_create_session_returns_201(authed_client, mocker):
    mocker.patch(f"{SVC}.create_session", return_value=_SESSION)
    resp = authed_client.post("/sessions", json={"session_type": "regular"})
    assert resp.status_code == 201


def test_create_session_response_has_id(authed_client, mocker):
    mocker.patch(f"{SVC}.create_session", return_value=_SESSION)
    resp = authed_client.post("/sessions", json={})
    assert "id" in resp.get_json()


# ── rename ────────────────────────────────────────────────────────────────────

def test_rename_session_returns_204(authed_client, mocker):
    mocker.patch(f"{SVC}.rename_session", return_value=None)
    resp = authed_client.patch("/sessions/sess-1", json={"title": "New Title"})
    assert resp.status_code == 204


def test_rename_session_missing_title_returns_422(authed_client):
    resp = authed_client.patch("/sessions/sess-1", json={})
    assert resp.status_code == 422


def test_rename_session_empty_title_returns_422(authed_client):
    resp = authed_client.patch("/sessions/sess-1", json={"title": "   "})
    assert resp.status_code == 422


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_session_returns_204(authed_client, mocker):
    mocker.patch(f"{SVC}.delete_session", return_value=None)
    resp = authed_client.delete("/sessions/sess-1")
    assert resp.status_code == 204


# ── messages ──────────────────────────────────────────────────────────────────

def test_get_messages_returns_list(authed_client, mocker):
    mocker.patch(f"{SVC}.get_messages", return_value=[_MSG])
    resp = authed_client.get("/sessions/sess-1/messages")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


# ── partials ──────────────────────────────────────────────────────────────────

def test_session_list_partial_requires_auth(client):
    resp = client.get("/sessions/partial")
    assert resp.status_code in (302, 204)  # redirect to login


def test_session_list_partial_renders_html(authed_client, mocker):
    mocker.patch(f"{SVC}.list_sessions", return_value=[_SESSION])
    resp = authed_client.get("/sessions/partial")
    assert resp.status_code == 200
    assert b"Test Session" in resp.data


def test_knowledge_tree_partial_renders(authed_client, mocker):
    tree_node = {**_SESSION, "depth_offset": 0, "is_current": True}
    mocker.patch(f"{SVC}.get_knowledge_tree", return_value=[tree_node])
    resp = authed_client.get("/sessions/sess-uuid-1/knowledge-tree/partial")
    assert resp.status_code == 200
    assert b"Knowledge Tree" in resp.data


# ── regenerate ────────────────────────────────────────────────────────────────

def test_regenerate_session_requires_auth(client):
    assert client.post("/sessions/sess-1/regenerate").status_code == 401


def test_regenerate_session_returns_result(authed_client, mocker):
    mocker.patch(f"{SVC}.regenerate_session", return_value={"session_id": "sess-2", "status": "regenerated"})
    resp = authed_client.post("/sessions/sess-1/regenerate")
    assert resp.status_code == 200
    assert resp.get_json()["session_id"] == "sess-2"


def test_regenerate_session_calls_service_with_user_and_session(authed_client, mocker):
    mock = mocker.patch(f"{SVC}.regenerate_session", return_value={"session_id": "sess-1"})
    authed_client.post("/sessions/sess-1/regenerate")
    mock.assert_called_once_with("user-uuid-1234", "sess-1")


# ── get_tree ──────────────────────────────────────────────────────────────────

def test_get_tree_requires_auth(client):
    assert client.get("/sessions/sess-1/tree").status_code == 401


def test_get_tree_returns_list(authed_client, mocker):
    mocker.patch(f"{SVC}.get_tree", return_value=[_SESSION])
    resp = authed_client.get("/sessions/sess-uuid-1/tree")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_get_tree_returns_empty_list(authed_client, mocker):
    mocker.patch(f"{SVC}.get_tree", return_value=[])
    resp = authed_client.get("/sessions/sess-uuid-1/tree")
    assert resp.status_code == 200
    assert resp.get_json() == []


# ── tree_partial ──────────────────────────────────────────────────────────────

def test_tree_partial_requires_auth(client):
    assert client.get("/sessions/sess-1/tree/partial").status_code == 302


def test_tree_partial_renders(authed_client, mocker):
    mocker.patch(f"{SVC}.get_tree", return_value=[_SESSION])
    resp = authed_client.get("/sessions/sess-uuid-1/tree/partial")
    assert resp.status_code == 200


# ── messages_partial ──────────────────────────────────────────────────────────

def test_messages_partial_requires_auth(client):
    assert client.get("/sessions/sess-1/messages/partial").status_code == 302


def test_messages_partial_renders_regular_session(authed_client, mocker):
    mocker.patch(f"{SVC}.get_session", return_value={**_SESSION, "session_type": "regular"})
    mocker.patch(f"{SVC}.get_messages", return_value=[_MSG])
    resp = authed_client.get("/sessions/sess-uuid-1/messages/partial")
    assert resp.status_code == 200


def test_messages_partial_renders_quiz_inline_when_attempt_linked(authed_client, mocker):
    quiz_sess = {**_SESSION, "session_type": "quiz", "linked_attempt_id": "attempt-1"}
    mocker.patch(f"{SVC}.get_session", return_value=quiz_sess)
    mocker.patch("backend.api.quiz.service.get_attempt", return_value={
        "attempt_id": "attempt-1", "session_id": "sess-uuid-1",
        "questions": [], "answers": {}, "score": None, "completed_at": None,
    })
    resp = authed_client.get("/sessions/sess-uuid-1/messages/partial")
    assert resp.status_code == 200


def test_messages_partial_falls_back_to_messages_for_quiz_without_attempt(authed_client, mocker):
    quiz_sess = {**_SESSION, "session_type": "quiz", "linked_attempt_id": None}
    mocker.patch(f"{SVC}.get_session", return_value=quiz_sess)
    mocker.patch(f"{SVC}.get_messages", return_value=[_MSG])
    resp = authed_client.get("/sessions/sess-uuid-1/messages/partial")
    assert resp.status_code == 200


def test_messages_partial_renders_news_discussion_session(authed_client, mocker):
    news_sess = {
        **_SESSION,
        "session_type": "news_discussion",
        "topic": "https://example.com/article",
        "title": "AI Takes Over",
    }
    mocker.patch(f"{SVC}.get_session", return_value=news_sess)
    mocker.patch(f"{SVC}.get_messages", return_value=[_MSG])
    resp = authed_client.get("/sessions/sess-uuid-1/messages/partial")
    assert resp.status_code == 200
