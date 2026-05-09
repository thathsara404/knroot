from __future__ import annotations

import json
import logging

from flask import Blueprint, Response, g, stream_with_context

from backend.core.auth import require_auth
from backend.core.sse import (
    KEEPALIVE_INTERVAL,
    register_user,
    renew_user_ttl,
    unregister_user,
)
from backend.extensions import get_redis

logger = logging.getLogger(__name__)

bp = Blueprint("events", __name__)


@bp.get("/events/stream")
@require_auth
def event_stream():
    """Long-lived Server-Sent Events stream for the authenticated user.

    Uses get_message(timeout=KEEPALIVE_INTERVAL) so the generator wakes up
    periodically even with no events.  On each idle tick it:
      - yields an SSE comment line (":<space>keepalive\\n\\n") to keep the
        connection alive through proxies/load-balancers that close idle streams
      - renews the per-user TTL presence key in Redis

    This means a crashed process leaves a presence key that expires within
    PRESENCE_TTL seconds rather than living forever in a SET.
    """
    user_id = g.user_id

    def generate():
        register_user(user_id)
        pubsub = get_redis().pubsub()
        try:
            pubsub.subscribe(f"sse:user:{user_id}")
            while True:
                message = pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=KEEPALIVE_INTERVAL,
                )
                if message and message.get("type") == "message":
                    try:
                        data = json.loads(message["data"])
                        yield f"event: {data['event']}\ndata: {data['payload']}\n\n"
                    except (ValueError, KeyError, TypeError) as exc:
                        logger.warning("sse.stream invalid message: %s", exc)
                else:
                    # Idle tick — send keepalive comment and renew TTL
                    yield ": keepalive\n\n"
                    renew_user_ttl(user_id)
        finally:
            try:
                pubsub.unsubscribe()
                pubsub.close()
            except Exception as exc:
                logger.warning("sse.stream pubsub cleanup failed: %s", exc)
            unregister_user(user_id)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
