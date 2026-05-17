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
    assert val["type"] == "sectioned"
    assert val["sections"][0]["id"] == "s1"
    # _normalise_sectioned backfills these defaults
    assert val["hierarchy_diagram"] == ""
    assert val["sections"][0]["artifacts"] == []


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
    assert val["type"] == "sectioned"
    assert val["sections"][0]["id"] == "s1"
    # fence stripping works; normalisation still applies
    assert val["hierarchy_diagram"] == ""
    assert val["sections"][0]["artifacts"] == []


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


# ── _parse_llm_response — hierarchy_diagram + artifacts normalisation ─────────

def test_parse_sectioned_missing_hierarchy_diagram_defaults_to_empty_string():
    data = {"type": "sectioned", "sections": [{"id": "s1", "title": "T", "content": "C"}]}
    val, typ = _parse_llm_response(_json.dumps(data))
    assert typ == "sectioned"
    assert val["hierarchy_diagram"] == ""


def test_parse_sectioned_preserves_hierarchy_diagram_when_present():
    diagram = "flowchart TD\n  ROOT[ML] --> A[SGD]\n  ROOT --> B[Adam]"
    data = {"type": "sectioned", "hierarchy_diagram": diagram,
            "sections": [{"id": "s1", "title": "SGD", "content": "C"}]}
    val, typ = _parse_llm_response(_json.dumps(data))
    assert val["hierarchy_diagram"] == diagram


def test_parse_sectioned_missing_artifacts_defaults_to_empty_list():
    data = {"type": "sectioned", "sections": [{"id": "s1", "title": "T", "content": "C"}]}
    val, _ = _parse_llm_response(_json.dumps(data))
    assert val["sections"][0]["artifacts"] == []


def test_parse_sectioned_keeps_all_valid_artifact_types():
    artifacts = [
        {"type": "formula", "latex": "E=mc^2", "caption": "Energy"},
        {"type": "chart", "chart_type": "line", "labels": [], "datasets": []},
        {"type": "diagram", "mermaid": "flowchart LR\n  A --> B", "caption": "Flow"},
    ]
    data = {"type": "sectioned",
            "sections": [{"id": "s1", "title": "T", "content": "C", "artifacts": artifacts}]}
    val, _ = _parse_llm_response(_json.dumps(data))
    assert len(val["sections"][0]["artifacts"]) == 3


def test_parse_sectioned_filters_invalid_artifact_types():
    artifacts = [
        {"type": "formula", "latex": "x^2"},
        {"type": "INVALID"},
        {"type": "unknown", "data": "bad"},
    ]
    data = {"type": "sectioned",
            "sections": [{"id": "s1", "title": "T", "content": "C", "artifacts": artifacts}]}
    val, _ = _parse_llm_response(_json.dumps(data))
    kept = val["sections"][0]["artifacts"]
    assert len(kept) == 1
    assert kept[0]["type"] == "formula"


def test_parse_sectioned_empty_artifacts_list_preserved():
    data = {"type": "sectioned",
            "sections": [{"id": "s1", "title": "T", "content": "C", "artifacts": []}]}
    val, _ = _parse_llm_response(_json.dumps(data))
    assert val["sections"][0]["artifacts"] == []


def test_parse_sectioned_all_sections_get_artifacts_default():
    data = {
        "type": "sectioned",
        "sections": [
            {"id": "s1", "title": "T1", "content": "C"},
            {"id": "s2", "title": "T2", "content": "C"},
            {"id": "s3", "title": "T3", "content": "C",
             "artifacts": [{"type": "formula", "latex": "x"}]},
        ],
    }
    val, _ = _parse_llm_response(_json.dumps(data))
    assert val["sections"][0]["artifacts"] == []
    assert val["sections"][1]["artifacts"] == []
    assert len(val["sections"][2]["artifacts"]) == 1


# ── template rendering — hierarchy chart and artifact zones ───────────────────

# Rich fixture: includes hierarchy_diagram and formula + chart artifacts on s1.
_SECTIONED_RICH = {
    "response": {
        "type": "sectioned",
        "intro": "Overview of the topic.",
        "hierarchy_diagram": (
            "flowchart TD\n"
            "  ROOT[Machine Learning] --> S1[Gradient Descent]\n"
            "  ROOT --> S2[Applications]"
        ),
        "sections": [
            {
                "id": "s1",
                "title": "Gradient Descent",
                "content": "Optimization via $\\nabla J(\\theta)$.",
                "key_points": ["Iterative", "Gradient-based"],
                "misconception": "Not always slow.",
                "learn_more_topic": "SGD variants",
                "artifacts": [
                    {
                        "type": "formula",
                        "latex": "\\theta := \\theta - \\alpha \\nabla J(\\theta)",
                        "caption": "Parameter update rule",
                    },
                    {
                        "type": "chart",
                        "chart_type": "line",
                        "title": "Training Loss",
                        "labels": ["Epoch 1", "Epoch 2", "Epoch 3"],
                        "datasets": [{"label": "Loss", "data": [0.9, 0.6, 0.3]}],
                        "caption": "Loss decreases over epochs",
                    },
                ],
            },
            {
                "id": "s2",
                "title": "Applications",
                "content": "Used widely in ML.",
                "key_points": ["Neural networks"],
                "misconception": "Not just NN.",
                "learn_more_topic": "NLP applications",
                "artifacts": [],
            },
        ],
        "outro": "Start with Gradient Descent.",
    },
    "response_type": "sectioned",
    "session_id": "sess-1",
    "is_new_conversation": True,
    "suggested_topics": [],
}


def test_chat_htmx_rich_renders_hierarchy_diagram_wrapper(authed_client, mocker):
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value=_SECTIONED_RICH)
    mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Explain ML"}, headers=HTMX)
    assert b"hierarchy-diagram-wrapper" in resp.data


def test_chat_htmx_rich_renders_section_title_data_attribute(authed_client, mocker):
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value=_SECTIONED_RICH)
    mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Explain ML"}, headers=HTMX)
    assert b"data-section-title" in resp.data


def test_chat_htmx_rich_renders_formula_artifact_toggle(authed_client, mocker):
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value=_SECTIONED_RICH)
    mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Explain ML"}, headers=HTMX)
    assert b"Show Formula" in resp.data


def test_chat_htmx_rich_renders_chart_artifact_toggle(authed_client, mocker):
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value=_SECTIONED_RICH)
    mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Explain ML"}, headers=HTMX)
    assert b"Show Chart" in resp.data


def test_chat_htmx_rich_renders_katex_block_for_formula(authed_client, mocker):
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value=_SECTIONED_RICH)
    mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Explain ML"}, headers=HTMX)
    assert b"katex-block" in resp.data


def test_chat_htmx_rich_renders_chart_canvas(authed_client, mocker):
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value=_SECTIONED_RICH)
    mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Explain ML"}, headers=HTMX)
    assert b"artifact-chart" in resp.data


def test_chat_htmx_plain_sectioned_no_hierarchy_when_absent(authed_client, mocker):
    # _SECTIONED fixture has no hierarchy_diagram — wrapper must not render
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value=_SECTIONED)
    mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Explain it"}, headers=HTMX)
    assert b"hierarchy-diagram-wrapper" not in resp.data


def test_chat_htmx_plain_sectioned_no_artifact_toggles_when_absent(authed_client, mocker):
    # _SECTIONED fixture has no artifacts — no toggle buttons must appear
    mocker.patch(f"{CHAT_ROUTES}.get_or_create_session", return_value="sess-1")
    mocker.patch(f"{CHAT_ROUTES}.send_message", return_value=_SECTIONED)
    mocker.patch(f"{CHAT_ROUTES}.auto_title_session")
    resp = authed_client.post("/chat", json={"message": "Explain it"}, headers=HTMX)
    assert b"Show Formula" not in resp.data
    assert b"Show Chart" not in resp.data
    assert b"Show Diagram" not in resp.data


# ── /chat/quiz-section — template rendering ───────────────────────────────────

import json as _json_mod

_LLM_PATCH = "backend.core.llm.build_llm_client"

_SECTION_QUESTIONS = [
    {"id": "q1", "text": "What does gradient descent minimise?",
     "options": ["Loss function", "Accuracy", "Weights", "Bias"], "correct": 0},
    {"id": "q2", "text": "What triggers the vanishing gradient problem?",
     "options": ["Deep networks", "Dropout", "BatchNorm", "Adam"], "correct": 0},
]


def test_quiz_section_success_returns_200(authed_client, mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.invoke.return_value = mocker.MagicMock(
        content=_json_mod.dumps({"questions": _SECTION_QUESTIONS})
    )
    mocker.patch(_LLM_PATCH, return_value=mock_llm)
    resp = authed_client.post("/chat/quiz-section", json={
        "session_id": "sess-1",
        "section_id": "s1",
        "section_content": "Gradient descent is an iterative optimisation algorithm.",
    })
    assert resp.status_code == 200


def test_quiz_section_renders_quick_quiz_header(authed_client, mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.invoke.return_value = mocker.MagicMock(
        content=_json_mod.dumps({"questions": _SECTION_QUESTIONS})
    )
    mocker.patch(_LLM_PATCH, return_value=mock_llm)
    resp = authed_client.post("/chat/quiz-section", json={
        "session_id": "sess-1",
        "section_id": "s1",
        "section_content": "Gradient descent is an iterative optimisation algorithm.",
    })
    assert b"Quick Quiz" in resp.data


def test_quiz_section_renders_section_id_in_container(authed_client, mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.invoke.return_value = mocker.MagicMock(
        content=_json_mod.dumps({"questions": _SECTION_QUESTIONS})
    )
    mocker.patch(_LLM_PATCH, return_value=mock_llm)
    resp = authed_client.post("/chat/quiz-section", json={
        "session_id": "sess-1",
        "section_id": "my-section-42",
        "section_content": "Gradient descent is an iterative optimisation algorithm.",
    })
    assert b"my-section-42" in resp.data


def test_quiz_section_llm_failure_returns_graceful_fallback(authed_client, mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.invoke.side_effect = Exception("LLM timeout")
    mocker.patch(_LLM_PATCH, return_value=mock_llm)
    resp = authed_client.post("/chat/quiz-section", json={
        "session_id": "sess-1",
        "section_id": "s1",
        "section_content": "Some content about ML optimisation techniques.",
    })
    assert resp.status_code == 200
    assert b"Could not generate quiz" in resp.data


def test_quiz_section_invalid_json_from_llm_returns_graceful_fallback(authed_client, mocker):
    mock_llm = mocker.MagicMock()
    mock_llm.invoke.return_value = mocker.MagicMock(content="not valid json {{{{")
    mocker.patch(_LLM_PATCH, return_value=mock_llm)
    resp = authed_client.post("/chat/quiz-section", json={
        "session_id": "sess-1",
        "section_id": "s1",
        "section_content": "Content about ML optimisation and backpropagation.",
    })
    assert resp.status_code == 200
    assert b"Could not generate quiz" in resp.data
