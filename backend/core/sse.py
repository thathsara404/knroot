from __future__ import annotations

import json
import logging

from backend.extensions import get_redis

logger = logging.getLogger(__name__)

# Per-user presence keys: sse:online:<user_id>  (value "1", TTL = PRESENCE_TTL seconds)
# Renewed every KEEPALIVE_INTERVAL seconds by the SSE generator's idle tick.
# Expires automatically if the connection is dropped without a clean disconnect.
PRESENCE_TTL = 30          # seconds until a presence key expires
KEEPALIVE_INTERVAL = 20.0  # seconds between idle keepalive ticks in the generator


def _channel(user_id: str) -> str:
    return f"sse:user:{user_id}"


def _presence_key(user_id: str) -> str:
    return f"sse:online:{user_id}"


def register_user(user_id: str) -> None:
    """Mark user as having an active SSE connection (TTL-based, self-healing)."""
    try:
        get_redis().setex(_presence_key(str(user_id)), PRESENCE_TTL, "1")
    except Exception as exc:
        logger.warning("sse.register_user failed user_id=%s: %s", user_id, exc)


def renew_user_ttl(user_id: str) -> None:
    """Renew the presence TTL — called on every keepalive tick."""
    try:
        get_redis().expire(_presence_key(str(user_id)), PRESENCE_TTL)
    except Exception as exc:
        logger.warning("sse.renew_user_ttl failed user_id=%s: %s", user_id, exc)


def unregister_user(user_id: str) -> None:
    """Remove presence key on clean disconnect."""
    try:
        get_redis().delete(_presence_key(str(user_id)))
    except Exception as exc:
        logger.warning("sse.unregister_user failed user_id=%s: %s", user_id, exc)


def publish_event(user_id: str, event: str, payload: dict) -> None:
    """Publish an SSE event to a single user's channel.

    Fire-and-forget: any Redis failure is logged but never raised.
    """
    try:
        get_redis().publish(
            _channel(str(user_id)),
            json.dumps({"event": event, "payload": json.dumps(payload)}),
        )
    except Exception as exc:
        logger.warning("sse.publish_event failed user_id=%s event=%s: %s",
                       user_id, event, exc)


def broadcast_event(event: str, payload: dict) -> None:
    """Publish an SSE event to every user with an active presence key.

    Uses SCAN over sse:online:* keys so stale SET entries can never accumulate.
    Fire-and-forget: silently skips on any Redis failure.
    """
    try:
        redis = get_redis()
        msg = json.dumps({"event": event, "payload": json.dumps(payload)})
        for key in redis.scan_iter("sse:online:*"):
            # key is "sse:online:<user_id>" — extract the user_id suffix
            if isinstance(key, bytes):
                key = key.decode()
            uid = key.split(":", 2)[-1]
            try:
                redis.publish(_channel(uid), msg)
            except Exception as exc:
                logger.warning("sse.broadcast_event publish failed user_id=%s: %s", uid, exc)
    except Exception as exc:
        logger.warning("sse.broadcast_event scan failed: %s", exc)
