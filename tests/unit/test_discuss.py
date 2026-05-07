"""Unit tests for discuss (Explore / Learn More) routes."""
import pytest

SVC = "backend.api.discuss.service"
HTMX = {"HX-Request": "true"}

_DISCUSS_RESULT = {
    "session_id": "sess-discuss-1",
    "thread_id": "thread-discuss-1",
    "title": "Test Article",
    "first_response": {
        "type": "sectioned",
        "intro": "This article touches on several principles.",
        "sections": [
            {"id": "s1", "title": "Constitutional Law", "content": "Details here.", "learn_more_topic": "Constitutional Law"}
        ],
        "outro": "These principles form the basis.",
    },
}

_LEARN_RESULT = {
    "session_id": "sess-learn-1",
    "thread_id": "thread-learn-1",
    "title": "Constitutional Law",
    "first_response": {
        "type": "sectioned",
        "intro": "Constitutional law overview.",
        "sections": [],
        "outro": "Done.",
    },
}


# ── auth guards ───────────────────────────────────────────────────────────────

def test_news_discuss_requires_auth(client):
    resp = client.post("/news/discuss", json={"article_id": "1", "article_title": "T", "article_link": "http://x"})
    assert resp.status_code == 401


def test_learn_more_requires_auth(client):
    resp = client.post("/sessions/sess-1/learn-more", json={"topic": "Topic"})
    assert resp.status_code == 401


# ── /news/discuss validation ──────────────────────────────────────────────────

def test_news_discuss_missing_all_fields_returns_422(authed_client):
    resp = authed_client.post("/news/discuss", json={})
    assert resp.status_code == 422


def test_news_discuss_missing_article_id_returns_422(authed_client):
    resp = authed_client.post("/news/discuss", json={"article_title": "T", "article_link": "http://x"})
    assert resp.status_code == 422


def test_news_discuss_missing_article_title_returns_422(authed_client):
    resp = authed_client.post("/news/discuss", json={"article_id": "1", "article_link": "http://x"})
    assert resp.status_code == 422


def test_news_discuss_missing_article_link_returns_422(authed_client):
    resp = authed_client.post("/news/discuss", json={"article_id": "1", "article_title": "T"})
    assert resp.status_code == 422


# ── /news/discuss success ─────────────────────────────────────────────────────

def test_news_discuss_json_returns_201(authed_client, mocker):
    mocker.patch(f"{SVC}.news_discuss", return_value=_DISCUSS_RESULT)
    resp = authed_client.post("/news/discuss", json={
        "article_id": "art-1",
        "article_title": "Test Article",
        "article_link": "https://test.com/article",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["session_id"] == "sess-discuss-1"


def test_news_discuss_htmx_returns_200_with_session_header(authed_client, mocker):
    mocker.patch(f"{SVC}.news_discuss", return_value=_DISCUSS_RESULT)
    resp = authed_client.post("/news/discuss", json={
        "article_id": "art-1",
        "article_title": "Test Article",
        "article_link": "https://test.com/article",
    }, headers=HTMX)
    assert resp.status_code == 200
    assert resp.headers.get("HX-Session-Id") == "sess-discuss-1"


def test_news_discuss_htmx_renders_section_title(authed_client, mocker):
    mocker.patch(f"{SVC}.news_discuss", return_value=_DISCUSS_RESULT)
    resp = authed_client.post("/news/discuss", json={
        "article_id": "art-1",
        "article_title": "Test Article",
        "article_link": "https://test.com/article",
    }, headers=HTMX)
    assert b"Constitutional Law" in resp.data


def test_news_discuss_calls_service_with_user_id(authed_client, mocker):
    mock = mocker.patch(f"{SVC}.news_discuss", return_value=_DISCUSS_RESULT)
    authed_client.post("/news/discuss", json={
        "article_id": "art-1",
        "article_title": "Test Article",
        "article_link": "https://test.com/article",
    })
    assert mock.call_args.kwargs.get("user_id") == "user-uuid-1234" or \
           mock.call_args.args[0] == "user-uuid-1234"


# ── /sessions/<id>/learn-more ─────────────────────────────────────────────────

def test_learn_more_missing_topic_returns_422(authed_client):
    resp = authed_client.post("/sessions/sess-1/learn-more", json={})
    assert resp.status_code == 422


def test_learn_more_empty_topic_returns_422(authed_client):
    resp = authed_client.post("/sessions/sess-1/learn-more", json={"topic": "   "})
    assert resp.status_code == 422


def test_learn_more_success_returns_201(authed_client, mocker):
    mocker.patch(f"{SVC}.create_learn_more", return_value=_LEARN_RESULT)
    resp = authed_client.post("/sessions/sess-1/learn-more", json={"topic": "Neural Networks"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["session_id"] == "sess-learn-1"


def test_learn_more_passes_topic_to_service(authed_client, mocker):
    mock = mocker.patch(f"{SVC}.create_learn_more", return_value=_LEARN_RESULT)
    authed_client.post("/sessions/sess-1/learn-more", json={"topic": "My Topic"})
    # topic should be passed as the last positional arg or keyword arg
    args = mock.call_args.args
    kwargs = mock.call_args.kwargs
    assert "My Topic" in args or kwargs.get("topic") == "My Topic"
