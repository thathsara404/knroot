"""Unit tests for backend.extensions — Redis helpers and session init."""
import pytest
from unittest.mock import MagicMock, patch


def test_get_redis_raises_when_not_initialised():
    import backend.extensions as ext
    original = ext.redis_client
    ext.redis_client = None
    try:
        from backend.extensions import get_redis
        with pytest.raises(RuntimeError, match="not initialised"):
            get_redis()
    finally:
        ext.redis_client = original


def test_init_redis_sets_global_client(monkeypatch):
    import fakeredis
    import backend.extensions as ext

    fake = fakeredis.FakeRedis(decode_responses=True)
    with patch("backend.extensions.redis.from_url", return_value=fake) as mock_from_url:
        from backend.extensions import init_redis
        result = init_redis("redis://localhost:6379/1")
        mock_from_url.assert_called_once_with("redis://localhost:6379/1", decode_responses=True)
        assert result is fake
        assert ext.redis_client is fake


def test_init_redis_return_value_usable_as_client(monkeypatch):
    import fakeredis
    fake = fakeredis.FakeRedis(decode_responses=True)
    with patch("backend.extensions.redis.from_url", return_value=fake):
        from backend.extensions import init_redis
        client = init_redis("redis://localhost/0")
        client.set("key", "val")
        assert client.get("key") == "val"


def test_init_session_configures_app(monkeypatch):
    import fakeredis
    mock_app = MagicMock()
    mock_app.config = {}  # real dict so __setitem__/__getitem__ work correctly
    fake_session_redis = fakeredis.FakeRedis(decode_responses=False)

    # Session is imported inside init_session's body, so patch the source module
    with patch("backend.extensions.redis.from_url", return_value=fake_session_redis), \
         patch("flask_session.Session") as mock_session_cls:
        from backend.extensions import init_session
        init_session(mock_app, "redis://localhost:6379/1")

        assert mock_app.config["SESSION_REDIS"] is fake_session_redis
        mock_session_cls.assert_called_once_with(mock_app)
