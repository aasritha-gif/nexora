from __future__ import annotations

import time

import pytest

from app.core.errors import RateLimitExceededError
from app.core.rate_limit import RateLimiter
from tests.conftest import FakeRedis


class TestLocalFallback:
    async def test_under_limit_passes(self):
        limiter = RateLimiter(limit=3, window_seconds=60)
        for _ in range(3):
            await limiter.check(None, "ip:1")

    async def test_over_limit_raises(self):
        limiter = RateLimiter(limit=3, window_seconds=60)
        for _ in range(3):
            await limiter.check(None, "ip:1")
        with pytest.raises(RateLimitExceededError):
            await limiter.check(None, "ip:1")

    async def test_keys_are_isolated(self):
        limiter = RateLimiter(limit=1, window_seconds=60)
        await limiter.check(None, "ip:1")
        with pytest.raises(RateLimitExceededError):
            await limiter.check(None, "ip:1")
        await limiter.check(None, "ip:2")  # different key unaffected

    async def test_expired_entries_trimmed_from_window(self):
        limiter = RateLimiter(limit=1, window_seconds=60)
        await limiter.check(None, "ip:1")
        # Age the stored entry beyond the window so the next call passes.
        bucket = limiter._local["ip:1"]
        bucket[0] = time.time() - 120
        await limiter.check(None, "ip:1")


class TestRedisPath:
    async def test_uses_incr_and_sets_expiry_once(self):
        redis = FakeRedis()
        limiter = RateLimiter(limit=5, window_seconds=60)
        await limiter.check(redis, "user:9")
        assert redis.values  # one counter created
        assert len(redis.expired) == 1  # expire only on first incr

    async def test_redis_limit_enforced(self):
        redis = FakeRedis()
        limiter = RateLimiter(limit=2, window_seconds=60)
        await limiter.check(redis, "user:9")
        await limiter.check(redis, "user:9")
        with pytest.raises(RateLimitExceededError):
            await limiter.check(redis, "user:9")

    async def test_redis_failure_falls_back_to_memory(self):
        redis = FakeRedis(fail=True)
        limiter = RateLimiter(limit=1, window_seconds=60)
        await limiter.check(redis, "user:9")
        with pytest.raises(RateLimitExceededError):
            await limiter.check(redis, "user:9")
