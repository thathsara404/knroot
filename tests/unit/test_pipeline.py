"""Unit tests for backend.agent.pipeline — pure helpers and mocked run_fact_check."""
import json
import sys
import pytest
from unittest.mock import MagicMock


# ── _classify_error ────────────────────────────────────────────────────────────

class TestClassifyError:
    def _fn(self, msg: str) -> str:
        from backend.agent.pipeline import _classify_error
        return _classify_error(Exception(msg))

    def test_429_is_quota_error(self):
        assert "quota" in self._fn("HTTP 429 Too Many Requests").lower()

    def test_resource_exhausted_is_quota_error(self):
        assert "quota" in self._fn("RESOURCE_EXHAUSTED").lower()

    def test_quota_keyword_is_quota_error(self):
        assert "quota" in self._fn("daily quota exceeded").lower()

    def test_403_is_invalid_key_error(self):
        result = self._fn("403 Forbidden")
        assert "invalid" in result.lower() or "key" in result.lower()

    def test_api_key_invalid_is_key_error(self):
        result = self._fn("API_KEY_INVALID")
        assert "invalid" in result.lower() or "key" in result.lower()

    def test_permission_denied_is_key_error(self):
        result = self._fn("permission denied for this key")
        assert "invalid" in result.lower() or "key" in result.lower()

    def test_404_is_model_not_found(self):
        result = self._fn("404 model not found")
        assert "model" in result.lower() or "found" in result.lower()

    def test_not_found_message_is_model_error(self):
        result = self._fn("resource not found in registry")
        assert "model" in result.lower() or "found" in result.lower()

    def test_unknown_error_returns_empty_string(self):
        from backend.agent.pipeline import _classify_error
        result = _classify_error(Exception("some random error"))
        assert result == ""


# ── _strip_citations ───────────────────────────────────────────────────────────

class TestStripCitations:
    def _fn(self, text: str) -> str:
        from backend.agent.pipeline import _strip_citations
        return _strip_citations(text)

    def test_removes_single_bracket_citation(self):
        assert self._fn("text [1] more") == "text  more"

    def test_removes_multi_number_citation(self):
        assert self._fn("text [1, 2] more") == "text  more"

    def test_no_citations_unchanged(self):
        assert self._fn("no citations here") == "no citations here"

    def test_removes_all_citations_in_string(self):
        result = self._fn("first [1] second [2, 3] end")
        assert "[" not in result and "]" not in result


# ── _fallback ──────────────────────────────────────────────────────────────────

class TestFallback:
    def _fn(self, title: str, reason: str = ""):
        from backend.agent.pipeline import _fallback
        return _fallback(title, reason)

    def test_always_returns_unverifiable_verdict(self):
        assert self._fn("Article")["overall_verdict"] == "unverifiable"

    def test_always_sets_error_flag(self):
        assert self._fn("Article")["error"] is True

    def test_always_returns_empty_claims(self):
        assert self._fn("Article")["claims"] == []

    def test_summary_includes_reason_when_given(self):
        result = self._fn("Test", "API quota exceeded")
        assert "API quota exceeded" in result["summary"]

    def test_summary_says_unavailable_when_no_reason(self):
        result = self._fn("Test")
        assert "unavailable" in result["summary"].lower()

    def test_summary_includes_article_title(self):
        result = self._fn("My Article")
        assert "My Article" in result["summary"]


# ── _merge_grounding_sources ───────────────────────────────────────────────────

class TestMergeGroundingSources:
    def _fn(self, data, response):
        from backend.agent.pipeline import _merge_grounding_sources
        _merge_grounding_sources(data, response)

    def _make_response(self, uris: list[str]):
        chunks = []
        for uri in uris:
            chunk = MagicMock()
            chunk.web.uri = uri
            chunks.append(chunk)
        gm = MagicMock()
        gm.grounding_chunks = chunks
        response = MagicMock()
        response.candidates = [MagicMock(grounding_metadata=gm)]
        return response

    def test_adds_urls_to_claims_without_sources(self):
        response = self._make_response(["http://example.com"])
        data = {"claims": [{"claim": "test", "sources": []}]}
        self._fn(data, response)
        assert len(data["claims"][0]["sources"]) > 0

    def test_does_not_overwrite_existing_sources(self):
        response = self._make_response(["http://new.com"])
        data = {"claims": [{"claim": "test", "sources": ["http://original.com"]}]}
        self._fn(data, response)
        assert data["claims"][0]["sources"] == ["http://original.com"]

    def test_no_chunks_leaves_claims_unchanged(self):
        gm = MagicMock()
        gm.grounding_chunks = []
        response = MagicMock()
        response.candidates = [MagicMock(grounding_metadata=gm)]
        data = {"claims": [{"claim": "test", "sources": []}]}
        self._fn(data, response)
        assert data["claims"][0]["sources"] == []

    def test_empty_candidates_does_not_raise(self):
        response = MagicMock()
        response.candidates = []
        data = {"claims": []}
        self._fn(data, response)  # should not raise

    def test_missing_grounding_metadata_does_not_raise(self):
        response = MagicMock()
        response.candidates = [MagicMock(grounding_metadata=None)]
        data = {"claims": []}
        self._fn(data, response)  # should not raise

    def test_multiple_claims_get_different_url_slices(self):
        response = self._make_response(["http://a.com", "http://b.com", "http://c.com"])
        data = {
            "claims": [
                {"claim": "c1", "sources": []},
                {"claim": "c2", "sources": []},
            ]
        }
        self._fn(data, response)
        # Both claims should have sources
        assert data["claims"][0]["sources"]
        assert data["claims"][1]["sources"]


# ── run_fact_check (mocked google.genai) ──────────────────────────────────────

@pytest.fixture
def google_genai_mock(monkeypatch):
    """Inject a mock google.genai module pair into sys.modules for the test."""
    mock_genai = MagicMock()
    mock_types = MagicMock()
    mock_google = MagicMock()
    mock_google.genai = mock_genai

    monkeypatch.setitem(sys.modules, "google", mock_google)
    monkeypatch.setitem(sys.modules, "google.genai", mock_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", mock_types)

    return mock_genai, mock_types


def _setup_response(mock_genai, text: str):
    mock_response = MagicMock()
    mock_response.text = text
    mock_response.candidates = []  # empty → _merge_grounding_sources is a no-op
    mock_genai.Client.return_value.models.generate_content.return_value = mock_response
    return mock_response


_VALID_JSON = json.dumps({
    "overall_verdict": "verified",
    "claims": [
        {"claim": "test claim", "verdict": "verified",
         "evidence": "multiple sources confirm", "sources": ["http://example.com"]},
    ],
    "summary": "The article is accurate.",
})


def test_run_fact_check_no_api_key_returns_fallback(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from backend.agent.pipeline import run_fact_check
    result = run_fact_check("Test Article", "Summary text", "http://example.com")
    assert result["overall_verdict"] == "unverifiable"
    assert result["error"] is True


def test_run_fact_check_client_init_failure_returns_fallback(monkeypatch, google_genai_mock):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    mock_genai, _ = google_genai_mock
    mock_genai.Client.side_effect = Exception("genai not available")
    from backend.agent.pipeline import run_fact_check
    result = run_fact_check("Test Article", "Summary text", "http://example.com")
    assert result["overall_verdict"] == "unverifiable"
    assert result["error"] is True


def test_run_fact_check_returns_verified_data(monkeypatch, google_genai_mock):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    mock_genai, _ = google_genai_mock
    _setup_response(mock_genai, _VALID_JSON)
    from backend.agent.pipeline import run_fact_check
    result = run_fact_check("Test Article", "Summary text", "http://example.com")
    assert result["overall_verdict"] == "verified"
    assert len(result["claims"]) == 1
    assert result["claims"][0]["claim"] == "test claim"


def test_run_fact_check_strips_markdown_fences(monkeypatch, google_genai_mock):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    mock_genai, _ = google_genai_mock
    fenced = "```json\n" + _VALID_JSON + "\n```"
    _setup_response(mock_genai, fenced)
    from backend.agent.pipeline import run_fact_check
    result = run_fact_check("Test Article", "Summary text", "http://example.com")
    assert result["overall_verdict"] == "verified"


def test_run_fact_check_empty_response_returns_fallback(monkeypatch, google_genai_mock):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    mock_genai, _ = google_genai_mock
    _setup_response(mock_genai, "")
    from backend.agent.pipeline import run_fact_check
    result = run_fact_check("Test Article", "Summary text", "http://example.com")
    assert result["overall_verdict"] == "unverifiable"
    assert result["error"] is True


def test_run_fact_check_wrong_json_keys_returns_fallback(monkeypatch, google_genai_mock):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    mock_genai, _ = google_genai_mock
    _setup_response(mock_genai, json.dumps({"unexpected_key": "value"}))
    from backend.agent.pipeline import run_fact_check
    result = run_fact_check("Test Article", "Summary text", "http://example.com")
    assert result["overall_verdict"] == "unverifiable"
    assert result["error"] is True


def test_run_fact_check_api_exception_returns_fallback(monkeypatch, google_genai_mock):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    mock_genai, _ = google_genai_mock
    mock_genai.Client.return_value.models.generate_content.side_effect = RuntimeError("API error")
    from backend.agent.pipeline import run_fact_check
    result = run_fact_check("Test Article", "Summary text", "http://example.com")
    assert result["overall_verdict"] == "unverifiable"
    assert result["error"] is True


def test_run_fact_check_quota_error_in_reason(monkeypatch, google_genai_mock):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    mock_genai, _ = google_genai_mock
    mock_genai.Client.return_value.models.generate_content.side_effect = Exception(
        "429 RESOURCE_EXHAUSTED quota"
    )
    from backend.agent.pipeline import run_fact_check
    result = run_fact_check("Test Article", "Summary text", "http://example.com")
    assert result["error"] is True
    assert "quota" in result["summary"].lower()


def test_run_fact_check_uses_custom_model_env_var(monkeypatch, google_genai_mock):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    monkeypatch.setenv("FACT_CHECK_MODEL", "gemini-2.5-pro")
    mock_genai, _ = google_genai_mock
    _setup_response(mock_genai, _VALID_JSON)
    from backend.agent.pipeline import run_fact_check
    run_fact_check("Test Article", "Summary", "http://example.com")
    call_kwargs = mock_genai.Client.return_value.models.generate_content.call_args
    assert "gemini-2.5-pro" in str(call_kwargs)
