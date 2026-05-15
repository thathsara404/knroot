"""Unit tests for the /health endpoint and global error handlers."""


def test_health_returns_ok_when_db_connected(client, mocker):
    mock_conn = mocker.MagicMock()
    mock_pool = mocker.MagicMock()
    mock_pool.connection.return_value.__enter__ = mocker.Mock(return_value=mock_conn)
    mock_pool.connection.return_value.__exit__ = mocker.Mock(return_value=False)
    mocker.patch("backend.api.health.routes.get_pool", return_value=mock_pool)

    resp = client.get("/health")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"


def test_health_returns_503_when_db_fails(client, mocker):
    mock_pool = mocker.MagicMock()
    mock_pool.connection.side_effect = Exception("connection refused")
    mocker.patch("backend.api.health.routes.get_pool", return_value=mock_pool)

    resp = client.get("/health")

    assert resp.status_code == 503
    data = resp.get_json()
    assert data["status"] == "error"
    assert "connection refused" in data["db"]


# ── global error handlers (backend/core/errors.py) ────────────────────────────

def test_404_handler_returns_json_not_found(client):
    resp = client.get("/this-route-does-not-exist-xyz-999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "Not found"


def test_405_handler_returns_json_method_not_allowed(client):
    # /health only registers GET; POST should trigger 405
    resp = client.post("/health")
    assert resp.status_code == 405
    assert "not allowed" in resp.get_json()["error"].lower()


# ── require_auth HTMX path (backend/core/auth.py lines 26-28) ─────────────────

def test_require_auth_htmx_unauthenticated_returns_204_hx_redirect(client):
    """HX-Request without a session → 204 + HX-Redirect header instead of 302."""
    resp = client.get("/events/stream", headers={"HX-Request": "true"})
    assert resp.status_code == 204
    assert "HX-Redirect" in resp.headers
    assert "/login" in resp.headers["HX-Redirect"]
