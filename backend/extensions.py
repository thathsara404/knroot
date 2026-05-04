from __future__ import annotations

import redis
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

redis_client: redis.Redis | None = None
limiter: Limiter = Limiter(key_func=get_remote_address)


def init_redis(redis_url: str) -> redis.Redis:
    global redis_client
    redis_client = redis.from_url(redis_url, decode_responses=True)
    return redis_client


def get_redis() -> redis.Redis:
    if redis_client is None:
        raise RuntimeError("Redis not initialised — call init_redis() first")
    return redis_client
