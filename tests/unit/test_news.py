"""Unit tests for news routes and cache helpers."""
import json
import pytest

NEWS_SVC = "backend.api.news.service"
PIPELINE = "backend.agent.pipeline"

_ARTICLE = {
    "id": "abc123def456",
    "source": "ArXiv AI",
    "title": "Test Article About Machine Learning",
    "link": "https://arxiv.org/abs/test",
    "summary": "A test summary about ML research.",
    "published": "2026-05-07T10:00:00",
}


# ── /news (public) ────────────────────────────────────────────────────────────

def test_news_endpoint_returns_200(client, mocker):
    mocker.patch(f"{NEWS_SVC}.get_news", return_value=[_ARTICLE])
    resp = client.get("/news?category=ai")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "articles" in data
    assert data["category"] == "ai"


def test_news_endpoint_invalid_category_returns_422(client):
    resp = client.get("/news?category=invalid")
    assert resp.status_code == 422


def test_news_endpoint_default_category_is_ai(client, mocker):
    mock = mocker.patch(f"{NEWS_SVC}.get_news", return_value=[])
    client.get("/news")
    mock.assert_called_with("ai", force=False)


# ── /news/partial (auth required) ────────────────────────────────────────────

def test_news_partial_requires_auth(client):
    resp = client.get("/news/partial")
    assert resp.status_code in (302, 204)


def test_news_partial_returns_html(authed_client, mocker):
    mocker.patch(f"{NEWS_SVC}.get_news", return_value=[_ARTICLE])
    resp = authed_client.get("/news/partial?category=ai")
    assert resp.status_code == 200
    assert b"Test Article" in resp.data


def test_news_partial_invalid_category_defaults_to_ai(authed_client, mocker):
    mock = mocker.patch(f"{NEWS_SVC}.get_news", return_value=[])
    authed_client.get("/news/partial?category=badcat")
    mock.assert_called_with("ai", force=False)


def test_news_partial_programming_category(authed_client, mocker):
    mock = mocker.patch(f"{NEWS_SVC}.get_news", return_value=[])
    authed_client.get("/news/partial?category=programming")
    mock.assert_called_with("programming", force=False)


def test_news_partial_political_category(authed_client, mocker):
    mock = mocker.patch(f"{NEWS_SVC}.get_news", return_value=[])
    authed_client.get("/news/partial?category=political")
    mock.assert_called_with("political", force=False)


# ── /news/fact-check ──────────────────────────────────────────────────────────

def test_fact_check_requires_auth(client):
    assert client.post("/news/fact-check", json={"article_title": "Test"}).status_code == 401


def test_fact_check_missing_title_returns_422(authed_client):
    resp = authed_client.post("/news/fact-check", json={})
    assert resp.status_code == 422


def test_fact_check_returns_200_json(authed_client, mocker):
    mocker.patch(f"{PIPELINE}.run_fact_check", return_value={
        "overall_verdict": "verified", "claims": [], "summary": "All verified."
    })
    resp = authed_client.post("/news/fact-check", json={"article_title": "Big AI News"})
    assert resp.status_code == 200


def test_fact_check_htmx_renders_template(authed_client, mocker):
    mocker.patch(f"{PIPELINE}.run_fact_check", return_value={
        "overall_verdict": "disputed", "claims": [], "summary": "Disputed findings."
    })
    resp = authed_client.post(
        "/news/fact-check",
        json={"article_title": "Test Article"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    # Template should render the summary
    assert b"Disputed findings." in resp.data


def test_fact_check_calls_pipeline_with_correct_args(authed_client, mocker):
    mock = mocker.patch(f"{PIPELINE}.run_fact_check", return_value={
        "overall_verdict": "verified", "claims": [], "summary": "OK"
    })
    authed_client.post("/news/fact-check", json={
        "article_title": "My Title",
        "article_summary": "My summary",
        "article_link": "https://example.com",
    })
    mock.assert_called_once_with("My Title", "My summary", "https://example.com")


# ── cache helpers ─────────────────────────────────────────────────────────────

def test_cache_set_and_get_cached(fresh_redis):
    from backend.api.news.cache import set_cache, get_cached
    set_cache(fresh_redis, "ai", [_ARTICLE])
    result = get_cached(fresh_redis, "ai")
    assert result is not None
    assert result[0]["id"] == "abc123def456"


def test_cache_miss_returns_none(fresh_redis):
    from backend.api.news.cache import get_cached
    # No data set — should return None
    result = get_cached(fresh_redis, "ai")
    assert result is None


def test_cache_stores_valid_json(fresh_redis):
    from backend.api.news.cache import set_cache
    set_cache(fresh_redis, "ai", [_ARTICLE])
    # Verify something was written to Redis
    keys = fresh_redis.keys("news:*:ai")
    assert len(keys) > 0
    raw = fresh_redis.get(keys[0])
    data = json.loads(raw)
    assert data[0]["title"] == "Test Article About Machine Learning"


def test_strip_html_removes_tags():
    from backend.api.news.cache import _strip_html
    result = _strip_html("<p>Hello <b>world</b> &amp; friends</p>")
    assert "<" not in result
    assert "Hello" in result
    assert "&" in result  # html.unescape converts &amp; → &


def test_article_id_is_12_chars():
    from backend.api.news.cache import _article_id
    result = _article_id("https://example.com/article/123")
    assert len(result) == 12
    assert result.isalnum()
