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
