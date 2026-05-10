"""Unit tests for the /health endpoint."""


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
