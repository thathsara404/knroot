"""Unit tests for quiz routes and generator validation."""
import pytest

SVC = "backend.api.quiz.service"

_Q = {"id": "q_01", "text": "What is gradient checkpointing?", "options": ["A", "B", "C", "D"], "topic": "Gradient"}
_Q_WITH_CORRECT = {**_Q, "correct": 1}

_ATTEMPT_OPEN = {
    "attempt_id": "attempt-1",
    "session_id": "sess-1",
    "questions": [_Q],
    "answers": {},
    "score": None,
    "completed_at": None,
}

_ATTEMPT_DONE = {
    **_ATTEMPT_OPEN,
    "questions": [_Q_WITH_CORRECT],
    "answers": {"q_01": 1},
    "score": 1,
    "completed_at": "2026-01-01T00:01:00",
}


# ── auth guards ───────────────────────────────────────────────────────────────

def test_generate_requires_auth(client):
    assert client.post("/quiz/generate", json={"session_id": "s"}).status_code == 401

def test_get_attempt_requires_auth(client):
    assert client.get("/quiz/attempt/attempt-1").status_code == 401

def test_save_answers_requires_auth(client):
    assert client.put("/quiz/attempt/attempt-1", json={}).status_code == 401

def test_retry_requires_auth(client):
    assert client.post("/quiz/retry", json={"attempt_id": "a"}).status_code == 401

def test_list_attempts_requires_auth(client):
    assert client.get("/quiz/attempts?session_id=s").status_code == 401

def test_relearn_requires_auth(client):
    assert client.get("/quiz/attempt/attempt-1/relearn/q_01").status_code == 401


# ── /quiz/generate ────────────────────────────────────────────────────────────

def test_generate_missing_session_returns_422(authed_client):
    resp = authed_client.post("/quiz/generate", json={})
    assert resp.status_code == 422


def test_generate_empty_session_returns_422(authed_client):
    resp = authed_client.post("/quiz/generate", json={"session_id": "   "})
    assert resp.status_code == 422


def test_generate_returns_attempt_id(authed_client, mocker):
    mocker.patch(f"{SVC}.generate_quiz", return_value={
        "attempt_id": "attempt-1", "questions": [_Q], "session_id": "sess-1"
    })
    resp = authed_client.post("/quiz/generate", json={"session_id": "sess-1"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["attempt_id"] == "attempt-1"
    assert "questions" in data


def test_generate_questions_lack_correct_field(authed_client, mocker):
    mocker.patch(f"{SVC}.generate_quiz", return_value={
        "attempt_id": "attempt-1",
        "questions": [_Q],  # _Q has no 'correct' field
        "session_id": "sess-1",
    })
    resp = authed_client.post("/quiz/generate", json={"session_id": "sess-1"})
    for q in resp.get_json()["questions"]:
        assert "correct" not in q


# ── /quiz/attempt/<id> GET ────────────────────────────────────────────────────

def test_get_open_attempt(authed_client, mocker):
    mocker.patch(f"{SVC}.get_attempt", return_value=_ATTEMPT_OPEN)
    resp = authed_client.get("/quiz/attempt/attempt-1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["attempt_id"] == "attempt-1"
    assert data["score"] is None


def test_get_completed_attempt_has_score(authed_client, mocker):
    mocker.patch(f"{SVC}.get_attempt", return_value=_ATTEMPT_DONE)
    resp = authed_client.get("/quiz/attempt/attempt-1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["score"] == 1
    assert data["completed_at"] is not None


# ── /quiz/attempt/<id> PUT ────────────────────────────────────────────────────

def test_save_answers_returns_saved(authed_client, mocker):
    mocker.patch(f"{SVC}.save_answers", return_value={"saved": True})
    resp = authed_client.put("/quiz/attempt/attempt-1", json={"answers": {"q_01": 1}})
    assert resp.status_code == 200
    assert resp.get_json()["saved"] is True


def test_submit_quiz_returns_score(authed_client, mocker):
    mocker.patch(f"{SVC}.save_answers", return_value={
        "score": 7, "total": 8,
        "questions": [_Q_WITH_CORRECT],
        "completed_at": "now",
    })
    resp = authed_client.put("/quiz/attempt/attempt-1", json={
        "answers": {"q_01": 1}, "completed": True
    })
    assert resp.status_code == 200
    assert resp.get_json()["score"] == 7


def test_submit_quiz_submit_flag(authed_client, mocker):
    mock = mocker.patch(f"{SVC}.save_answers", return_value={"saved": True})
    authed_client.put("/quiz/attempt/attempt-1", json={"answers": {}, "completed": True})
    assert mock.call_args.kwargs.get("submit") is True or mock.call_args.args[3] is True


# ── /quiz/retry ───────────────────────────────────────────────────────────────

def test_retry_missing_attempt_id_returns_422(authed_client):
    resp = authed_client.post("/quiz/retry", json={})
    assert resp.status_code == 422


def test_retry_returns_new_attempt_id(authed_client, mocker):
    mocker.patch(f"{SVC}.retry_quiz", return_value={"attempt_id": "attempt-2"})
    resp = authed_client.post("/quiz/retry", json={"attempt_id": "attempt-1"})
    assert resp.status_code == 200
    assert resp.get_json()["attempt_id"] == "attempt-2"


# ── /quiz/attempts GET ────────────────────────────────────────────────────────

def test_list_attempts_missing_session_returns_422(authed_client):
    resp = authed_client.get("/quiz/attempts")
    assert resp.status_code == 422


def test_list_attempts_returns_list(authed_client, mocker):
    mocker.patch(f"{SVC}.list_attempts", return_value=[
        {"attempt_id": "attempt-1", "score": 7, "attempted_at": "2026-01-01T00:00:00", "completed_at": None}
    ])
    resp = authed_client.get("/quiz/attempts?session_id=sess-1")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


# ── /quiz/attempt/<id>/relearn/<q_id> ────────────────────────────────────────

def test_relearn_returns_explanation(authed_client, mocker):
    mocker.patch(f"{SVC}.get_relearn", return_value={"explanation": "Because B is correct..."})
    resp = authed_client.get("/quiz/attempt/attempt-1/relearn/q_01")
    assert resp.status_code == 200
    assert resp.get_json()["explanation"] == "Because B is correct..."


# ── generator._validate ───────────────────────────────────────────────────────

def _make_questions(n: int, **overrides) -> list:
    q = {"id": "q_01", "text": "What is gradient checkpointing really?", "options": ["A", "B", "C", "D"], "correct": 0}
    q.update(overrides)
    return [dict(q, id=f"q_{i:02d}") for i in range(n)]


def test_validate_rejects_too_few_questions():
    from backend.api.quiz.generator import _validate
    with pytest.raises(ValueError, match="questions"):
        _validate(_make_questions(3), n_required=8)


def test_validate_rejects_wrong_option_count():
    from backend.api.quiz.generator import _validate
    qs = _make_questions(8, options=["A", "B"])
    with pytest.raises(ValueError, match="4 options"):
        _validate(qs, n_required=8)


def test_validate_rejects_invalid_correct_index():
    from backend.api.quiz.generator import _validate
    qs = _make_questions(8, correct=99)
    with pytest.raises(ValueError, match="correct"):
        _validate(qs, n_required=8)


def test_validate_rejects_short_question_text():
    from backend.api.quiz.generator import _validate
    qs = _make_questions(8, text="Short")
    with pytest.raises(ValueError, match="short"):
        _validate(qs, n_required=8)


def test_validate_accepts_valid_questions():
    from backend.api.quiz.generator import _validate
    _validate(_make_questions(8), n_required=8)  # must not raise


# ── generator._shuffle_options — pure function ────────────────────────────────

from backend.api.quiz.generator import _shuffle_options


def test_shuffle_preserves_correct_answer_text():
    q = {"text": "Question?", "options": ["A", "B", "C", "D"], "correct": 2}
    result = _shuffle_options(q)
    assert result["options"][result["correct"]] == "C"


def test_shuffle_preserves_all_option_values():
    q = {"text": "Question?", "options": ["A", "B", "C", "D"], "correct": 0}
    result = _shuffle_options(q)
    assert sorted(result["options"]) == ["A", "B", "C", "D"]


def test_shuffle_correct_index_stays_in_range():
    q = {"text": "Question?", "options": ["W", "X", "Y", "Z"], "correct": 3}
    result = _shuffle_options(q)
    assert 0 <= result["correct"] <= 3


def test_shuffle_preserves_non_option_fields():
    q = {"id": "q1", "text": "Question?", "options": ["A", "B", "C", "D"], "correct": 1, "topic": "ML"}
    result = _shuffle_options(q)
    assert result["id"] == "q1"
    assert result["topic"] == "ML"
    assert result["text"] == "Question?"


def test_shuffle_does_not_mutate_original():
    original_options = ["A", "B", "C", "D"]
    q = {"text": "Question?", "options": list(original_options), "correct": 0}
    _shuffle_options(q)
    assert q["options"] == original_options


def test_shuffle_correct_pointer_consistent_across_runs():
    q = {"text": "Question?", "options": ["A", "B", "C", "D"], "correct": 2}
    correct_text = q["options"][q["correct"]]
    for _ in range(20):
        result = _shuffle_options(q)
        assert result["options"][result["correct"]] == correct_text


# ── /quiz/generate-followup ───────────────────────────────────────────────────

def test_generate_followup_requires_auth(client):
    assert client.post("/quiz/generate-followup", json={"attempt_id": "a"}).status_code == 401


def test_generate_followup_missing_attempt_id_returns_422(authed_client):
    resp = authed_client.post("/quiz/generate-followup", json={})
    assert resp.status_code == 422


def test_generate_followup_returns_attempt_id(authed_client, mocker):
    mocker.patch(f"{SVC}.generate_quiz_followup", return_value={
        "attempt_id": "attempt-2", "questions": [_Q], "session_id": "sess-1",
    })
    resp = authed_client.post("/quiz/generate-followup", json={"attempt_id": "attempt-1"})
    assert resp.status_code == 200
    assert resp.get_json()["attempt_id"] == "attempt-2"


def test_generate_followup_calls_service_with_attempt_id(authed_client, mocker):
    mock = mocker.patch(f"{SVC}.generate_quiz_followup", return_value={
        "attempt_id": "attempt-2", "questions": [], "session_id": "sess-1",
    })
    authed_client.post("/quiz/generate-followup", json={"attempt_id": "attempt-1"})
    mock.assert_called_once()
    assert "attempt-1" in str(mock.call_args)


# ── /quiz/<attempt_id>/partial — template rendering ───────────────────────────

QUIZ_ROUTES = "backend.api.quiz.routes"


def test_quiz_inline_partial_requires_auth(client):
    assert client.get("/quiz/attempt-1/partial").status_code in (302, 401)


def test_quiz_inline_partial_renders_knowledge_check_heading(authed_client, mocker):
    mocker.patch(f"{SVC}.get_attempt", return_value=_ATTEMPT_OPEN)
    mocker.patch(f"{QUIZ_ROUTES}.query_one", return_value=None)
    resp = authed_client.get("/quiz/attempt-1/partial")
    assert resp.status_code == 200
    assert b"Knowledge Check" in resp.data


def test_quiz_inline_partial_renders_quiz_root_class(authed_client, mocker):
    mocker.patch(f"{SVC}.get_attempt", return_value=_ATTEMPT_OPEN)
    mocker.patch(f"{QUIZ_ROUTES}.query_one", return_value=None)
    resp = authed_client.get("/quiz/attempt-1/partial")
    assert b"knr-quiz-root" in resp.data


def test_quiz_inline_partial_uses_session_title_from_db(authed_client, mocker):
    mocker.patch(f"{SVC}.get_attempt", return_value=_ATTEMPT_OPEN)
    mocker.patch(f"{QUIZ_ROUTES}.query_one", side_effect=[
        {"title": "Gradient Descent Deep Dive"},  # session row
        None,                                      # quiz_session row
    ])
    resp = authed_client.get("/quiz/attempt-1/partial")
    assert b"Gradient Descent Deep Dive" in resp.data


def test_quiz_inline_partial_falls_back_to_knowledge_check_when_session_missing(
    authed_client, mocker
):
    mocker.patch(f"{SVC}.get_attempt", return_value=_ATTEMPT_OPEN)
    mocker.patch(f"{QUIZ_ROUTES}.query_one", return_value=None)  # session row not found
    resp = authed_client.get("/quiz/attempt-1/partial")
    assert b"Knowledge Check" in resp.data
