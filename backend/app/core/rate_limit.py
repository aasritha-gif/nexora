from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

import redis.asyncio as aioredis

from app.core.errors import RateLimitExceededError

log = logging.getLogger(__name__)


class RateLimiter:
    """Fixed-window rate limiter.

    Primary store is Redis (shared across processes). If Redis is unavailable,
    falls back to an in-process window map — logged loudly, never silently
    disabled.
    """

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._local: dict[str, deque[float]] = defaultdict(deque)
        self._last_redis_warning = 0.0

    async def check(self, redis: aioredis.Redis | None, key: str) -> None:
        now = time.time()
        window_start = now - self.window

        if redis is not None:
            try:
                redis_key = f"rl:{key}:{int(now // self.window)}"
                count = await redis.incr(redis_key)
                if count == 1:
                    await redis.expire(redis_key, self.window + 1)
                if count > self.limit:
                    raise RateLimitExceededError()
                return
            except RateLimitExceededError:
                raise
            except Exception:
                if now - self._last_redis_warning > 60:
                    log.warning(
                        "Rate limiter falling back to in-memory window (Redis unavailable)",
                        extra={"event": "rate_limit_redis_unavailable"},
                    )
                    self._last_redis_warning = now

        bucket = self._local[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= self.limit:
            raise RateLimitExceededError()
        bucket.append(now)
