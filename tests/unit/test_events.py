"""Unit tests for /events/stream route and backend.core.sse helpers."""
import json


# ── auth guard ────────────────────────────────────────────────────────────────

def test_event_stream_requires_auth(client):
    resp = client.get("/events/stream")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ── response headers ──────────────────────────────────────────────────────────
# The generator is an infinite loop, so we patch stream_with_context to return
# a finite replacement. This lets us check the Response object's headers without
# hanging or catching a propagated exception from the real generator.

def _patch_stream(mocker, *chunks):
    """Replace stream_with_context with a finite generator of the given chunks."""
    def fake_swc(gen):
        def _finite():
            yield from chunks
        return _finite()
    mocker.patch("backend.api.events.routes.stream_with_context", side_effect=fake_swc)


def test_event_stream_content_type_is_text_event_stream(authed_client, mocker):
    _patch_stream(mocker, b"")
    resp = authed_client.get("/events/stream")
    assert "text/event-stream" in resp.content_type


def test_event_stream_has_no_cache_header(authed_client, mocker):
    _patch_stream(mocker, b"")
    resp = authed_client.get("/events/stream")
    assert resp.headers.get("Cache-Control") == "no-cache"


def test_event_stream_has_accel_buffering_header(authed_client, mocker):
    _patch_stream(mocker, b"")
    resp = authed_client.get("/events/stream")
    assert resp.headers.get("X-Accel-Buffering") == "no"


# ── backend.core.sse helpers (tested via fakeredis) ───────────────────────────
# These tests cover the actual SSE logic: presence keys, TTL renewal, event
# publishing, and broadcasting. The fresh_redis fixture is autouse and provides
# the same FakeRedis instance that get_redis() returns during each test.

def test_register_user_sets_presence_key(fresh_redis):
    from backend.core.sse import register_user
    register_user("user-1")
    assert fresh_redis.get("sse:online:user-1") == "1"


def test_register_user_sets_ttl_on_key(fresh_redis):
    from backend.core.sse import register_user
    register_user("user-1")
    assert fresh_redis.ttl("sse:online:user-1") > 0


def test_unregister_user_removes_presence_key(fresh_redis):
    from backend.core.sse import register_user, unregister_user
    register_user("user-1")
    unregister_user("user-1")
    assert fresh_redis.get("sse:online:user-1") is None


def test_renew_user_ttl_keeps_key_alive(fresh_redis):
    from backend.core.sse import register_user, renew_user_ttl
    register_user("user-1")
    renew_user_ttl("user-1")
    assert fresh_redis.ttl("sse:online:user-1") > 0


def test_publish_event_delivers_to_channel(fresh_redis):
    from backend.core.sse import publish_event
    pubsub = fresh_redis.pubsub()
    pubsub.subscribe("sse:user:user-1")
    pubsub.get_message()  # consume the subscribe confirmation

    publish_event("user-1", "wall-update", {"count": 5})

    msg = pubsub.get_message()
    assert msg is not None
    data = json.loads(msg["data"])
    assert data["event"] == "wall-update"
    payload = json.loads(data["payload"])
    assert payload["count"] == 5


def test_publish_event_does_not_reach_other_user(fresh_redis):
    from backend.core.sse import publish_event
    pubsub = fresh_redis.pubsub()
    pubsub.subscribe("sse:user:user-2")
    pubsub.get_message()

    publish_event("user-1", "private-event", {})

    msg = pubsub.get_message()
    assert msg is None  # user-2 receives nothing


def test_broadcast_event_reaches_all_online_users(fresh_redis):
    from backend.core.sse import register_user, broadcast_event

    register_user("user-1")
    register_user("user-2")

    ps1 = fresh_redis.pubsub()
    ps2 = fresh_redis.pubsub()
    ps1.subscribe("sse:user:user-1")
    ps2.subscribe("sse:user:user-2")
    ps1.get_message()
    ps2.get_message()

    broadcast_event("new-post", {"share_id": "s1"})

    m1 = ps1.get_message()
    m2 = ps2.get_message()
    assert m1 is not None
    assert m2 is not None


def test_broadcast_event_skips_offline_users(fresh_redis):
    from backend.core.sse import broadcast_event
    # No users registered — no keys exist, broadcast is a no-op
    pubsub = fresh_redis.pubsub()
    pubsub.subscribe("sse:user:nobody")
    pubsub.get_message()

    broadcast_event("new-post", {})

    assert pubsub.get_message() is None


# ── sse.py exception-handler paths ───────────────────────────────────────────
# Each sse helper swallows exceptions. These tests exercise the except branches
# (lines 29-30, 37-38, 45-46, 59-60, 76, 80-83 in backend/core/sse.py).

def test_register_user_swallows_redis_error(mocker):
    mocker.patch("backend.core.sse.get_redis", side_effect=RuntimeError("no redis"))
    from backend.core.sse import register_user
    register_user("user-1")  # must not raise


def test_renew_user_ttl_swallows_redis_error(mocker):
    mocker.patch("backend.core.sse.get_redis", side_effect=RuntimeError("no redis"))
    from backend.core.sse import renew_user_ttl
    renew_user_ttl("user-1")  # must not raise


def test_unregister_user_swallows_redis_error(mocker):
    mocker.patch("backend.core.sse.get_redis", side_effect=RuntimeError("no redis"))
    from backend.core.sse import unregister_user
    unregister_user("user-1")  # must not raise


def test_publish_event_swallows_redis_error(mocker):
    mocker.patch("backend.core.sse.get_redis", side_effect=RuntimeError("no redis"))
    from backend.core.sse import publish_event
    publish_event("user-1", "test-event", {"x": 1})  # must not raise


def test_broadcast_event_handles_bytes_key(mocker):
    mock_redis = mocker.MagicMock()
    mock_redis.scan_iter.return_value = [b"sse:online:user-1"]
    mock_redis.publish.return_value = None
    mocker.patch("backend.core.sse.get_redis", return_value=mock_redis)

    from backend.core.sse import broadcast_event
    broadcast_event("test-event", {"x": 1})

    mock_redis.publish.assert_called_once()
    call_channel = mock_redis.publish.call_args[0][0]
    assert "user-1" in call_channel


def test_broadcast_event_swallows_inner_publish_error(mocker):
    mock_redis = mocker.MagicMock()
    mock_redis.scan_iter.return_value = ["sse:online:user-1"]
    mock_redis.publish.side_effect = RuntimeError("publish failed")
    mocker.patch("backend.core.sse.get_redis", return_value=mock_redis)

    from backend.core.sse import broadcast_event
    broadcast_event("test-event", {})  # must not raise


def test_broadcast_event_swallows_scan_error(mocker):
    mock_redis = mocker.MagicMock()
    mock_redis.scan_iter.side_effect = RuntimeError("redis scan failed")
    mocker.patch("backend.core.sse.get_redis", return_value=mock_redis)

    from backend.core.sse import broadcast_event
    broadcast_event("test-event", {})  # must not raise


# ── events/routes.py generate() body ─────────────────────────────────────────
# The SSE generator is an infinite loop. We capture it via stream_with_context
# and drive it manually with next() to cover lines 39-64.

def _capture_generator(mocker, authed_client):
    """Return the generate() closure without consuming it."""
    captured = []

    def fake_swc(gen):
        captured.append(gen)
        def finite():
            return
            yield
        return finite()

    mocker.patch("backend.api.events.routes.stream_with_context", side_effect=fake_swc)
    mocker.patch("backend.api.events.routes.KEEPALIVE_INTERVAL", 0)
    authed_client.get("/events/stream")
    assert captured, "stream_with_context was not called"
    return captured[0]


def test_generate_first_tick_yields_keepalive(authed_client, mocker, fresh_redis):
    gen = _capture_generator(mocker, authed_client)
    chunk = next(gen)
    assert chunk == ": keepalive\n\n"


def test_generate_yields_sse_event_on_published_message(authed_client, mocker, fresh_redis):
    gen = _capture_generator(mocker, authed_client)
    next(gen)  # consume keepalive so generator is past the first yield

    msg_data = json.dumps({
        "event": "test-event",
        "payload": json.dumps({"count": 7}),
    })
    fresh_redis.publish("sse:user:user-uuid-1234", msg_data)

    chunk = next(gen)
    assert "event: test-event" in chunk
    assert "count" in chunk


def test_generate_handles_invalid_message_and_continues(authed_client, mocker, fresh_redis):
    gen = _capture_generator(mocker, authed_client)
    next(gen)  # consume first keepalive

    # Publish an invalid JSON message
    fresh_redis.publish("sse:user:user-uuid-1234", "not valid json at all")

    # Generator should handle the exception internally and yield a keepalive
    chunk = next(gen)
    assert chunk == ": keepalive\n\n"


def test_generate_finally_block_runs_on_close(authed_client, mocker, fresh_redis):
    gen = _capture_generator(mocker, authed_client)
    next(gen)  # run past subscribe + first keepalive

    # Verify presence key was set by register_user inside the generator
    assert fresh_redis.get("sse:online:user-uuid-1234") == "1"

    # Closing triggers the finally block which calls unregister_user
    gen.close()

    # After close, presence key should be removed
    assert fresh_redis.get("sse:online:user-uuid-1234") is None


def test_generate_handles_pubsub_cleanup_error(authed_client, mocker, fresh_redis):
    """Cover lines 62-63: exception in pubsub.unsubscribe() is swallowed."""
    captured = []

    def fake_swc(gen):
        captured.append(gen)
        def finite():
            return
            yield
        return finite()

    mocker.patch("backend.api.events.routes.stream_with_context", side_effect=fake_swc)
    mocker.patch("backend.api.events.routes.KEEPALIVE_INTERVAL", 0)
    authed_client.get("/events/stream")
    gen = captured[0]

    # Mock pubsub that raises on cleanup so we hit the except in the finally block
    mock_pubsub = mocker.MagicMock()
    mock_pubsub.get_message.return_value = None
    mock_pubsub.unsubscribe.side_effect = RuntimeError("cleanup failed")
    mock_redis = mocker.MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub
    mocker.patch("backend.api.events.routes.get_redis", return_value=mock_redis)
    mocker.patch("backend.core.sse.get_redis", return_value=fresh_redis)

    next(gen)   # start the generator — calls register_user + subscribe + keepalive
    gen.close() # triggers finally → unsubscribe raises → caught by except (lines 62-63)
