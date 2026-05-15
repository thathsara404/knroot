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


# ── _normalise_sectioned — pure function ──────────────────────────────────────

import json as _json
from backend.api.discuss.service import _normalise_sectioned, _run_discussion_pipeline


def test_normalise_adds_hierarchy_diagram_default():
    data = {"type": "sectioned", "sections": [{"id": "s1", "title": "T"}]}
    _normalise_sectioned(data)
    assert data["hierarchy_diagram"] == ""


def test_normalise_preserves_existing_hierarchy_diagram():
    diagram = "flowchart TD\n  ROOT[Topic] --> A[Section]"
    data = {"type": "sectioned", "hierarchy_diagram": diagram, "sections": []}
    _normalise_sectioned(data)
    assert data["hierarchy_diagram"] == diagram


def test_normalise_adds_artifacts_default_to_each_section():
    data = {"type": "sectioned", "sections": [{"id": "s1"}, {"id": "s2"}]}
    _normalise_sectioned(data)
    assert data["sections"][0]["artifacts"] == []
    assert data["sections"][1]["artifacts"] == []


def test_normalise_filters_invalid_artifact_types():
    data = {
        "type": "sectioned",
        "sections": [{"id": "s1", "artifacts": [
            {"type": "formula", "latex": "x^2"},
            {"type": "HACK", "payload": "bad"},
        ]}],
    }
    _normalise_sectioned(data)
    kept = data["sections"][0]["artifacts"]
    assert len(kept) == 1
    assert kept[0]["type"] == "formula"


def test_normalise_handles_empty_sections_list():
    data = {"type": "sectioned", "sections": []}
    _normalise_sectioned(data)
    assert data["hierarchy_diagram"] == ""


def test_normalise_handles_missing_sections_key():
    data = {"type": "sectioned"}
    _normalise_sectioned(data)
    assert data["hierarchy_diagram"] == ""


# ── _run_discussion_pipeline — normalisation via mocked LLM ──────────────────

_DISCUSS_SVC = "backend.api.discuss.service"


def test_pipeline_adds_hierarchy_diagram_to_old_format(mocker):
    old = {"type": "sectioned", "sections": [{"id": "s1", "title": "T", "content": "C"}]}
    mock_llm = mocker.MagicMock()
    mock_llm.invoke.return_value.content = _json.dumps(old)
    mocker.patch(f"{_DISCUSS_SVC}.build_llm_client", return_value=mock_llm)

    result = _run_discussion_pipeline("test prompt")

    assert result["hierarchy_diagram"] == ""
    assert result["sections"][0]["artifacts"] == []


def test_pipeline_preserves_hierarchy_diagram_when_present(mocker):
    diagram = "flowchart TD\n  ROOT[AI] --> A[Foundations]"
    data = {
        "type": "sectioned",
        "hierarchy_diagram": diagram,
        "sections": [{"id": "s1", "title": "Foundations", "content": "C"}],
    }
    mock_llm = mocker.MagicMock()
    mock_llm.invoke.return_value.content = _json.dumps(data)
    mocker.patch(f"{_DISCUSS_SVC}.build_llm_client", return_value=mock_llm)

    result = _run_discussion_pipeline("test prompt")

    assert result["hierarchy_diagram"] == diagram


def test_pipeline_filters_invalid_artifact_types(mocker):
    data = {
        "type": "sectioned",
        "sections": [{"id": "s1", "title": "T", "content": "C", "artifacts": [
            {"type": "formula", "latex": "E=mc^2"},
            {"type": "INVALID_TYPE"},
        ]}],
    }
    mock_llm = mocker.MagicMock()
    mock_llm.invoke.return_value.content = _json.dumps(data)
    mocker.patch(f"{_DISCUSS_SVC}.build_llm_client", return_value=mock_llm)

    result = _run_discussion_pipeline("test prompt")

    kept = result["sections"][0]["artifacts"]
    assert len(kept) == 1
    assert kept[0]["type"] == "formula"


# ── template rendering — hierarchy + diagram artifact in discuss response ─────

# Rich fixture: hierarchy_diagram + a diagram artifact on s1.
_DISCUSS_RICH = {
    "session_id": "sess-discuss-1",
    "thread_id": "thread-discuss-1",
    "title": "Constitutional Case",
    "first_response": {
        "type": "sectioned",
        "intro": "This article touches on constitutional principles.",
        "hierarchy_diagram": (
            "flowchart TD\n"
            "  ROOT[Constitutional Law] --> A[Separation of Powers]\n"
            "  ROOT --> B[Judicial Review]"
        ),
        "sections": [
            {
                "id": "s1",
                "title": "Separation of Powers",
                "content": "The three branches of government are kept distinct.",
                "key_points": ["Executive", "Legislative", "Judicial"],
                "misconception": "Not an absolute separation.",
                "learn_more_topic": "Checks and Balances",
                "artifacts": [
                    {
                        "type": "diagram",
                        "mermaid": "flowchart TD\n  Exec --> Congress\n  Congress --> Courts\n  Courts --> Exec",
                        "caption": "Power flow between branches",
                    },
                ],
            },
            {
                "id": "s2",
                "title": "Judicial Review",
                "content": "Courts can strike down unconstitutional laws.",
                "key_points": ["Marbury v Madison"],
                "misconception": "Not explicitly in the Constitution.",
                "learn_more_topic": "Constitutional Interpretation",
                "artifacts": [],
            },
        ],
        "outro": "These principles form the foundation of modern governance.",
    },
}


def test_news_discuss_htmx_renders_hierarchy_diagram_wrapper(authed_client, mocker):
    mocker.patch(f"{SVC}.news_discuss", return_value=_DISCUSS_RICH)
    resp = authed_client.post("/news/discuss", json={
        "article_id": "art-1",
        "article_title": "Constitutional Case",
        "article_link": "https://test.com/article",
    }, headers=HTMX)
    assert b"hierarchy-diagram-wrapper" in resp.data


def test_news_discuss_htmx_renders_diagram_artifact_toggle(authed_client, mocker):
    mocker.patch(f"{SVC}.news_discuss", return_value=_DISCUSS_RICH)
    resp = authed_client.post("/news/discuss", json={
        "article_id": "art-1",
        "article_title": "Constitutional Case",
        "article_link": "https://test.com/article",
    }, headers=HTMX)
    assert b"Show Diagram" in resp.data
