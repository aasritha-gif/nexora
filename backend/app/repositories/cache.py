from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

log = logging.getLogger(__name__)


class CacheRepository:
    """Redis cache with TTLs. Values are plain strings (JSON at call sites).
    All operations degrade to None when Redis is unavailable — callers must
    treat a miss as a cache miss, never as an error."""

    def __init__(self, redis: aioredis.Redis | None):
        self.redis = redis

    @property
    def available(self) -> bool:
        return self.redis is not None

    async def get(self, key: str) -> str | None:
        if self.redis is None:
            return None
        try:
            return await self.redis.get(key)
        except Exception:
            return None

    async def set(self, key: str, value: str, *, ttl_seconds: int) -> bool:
        if self.redis is None:
            return False
        try:
            await self.redis.setex(key, ttl_seconds, value)
            return True
        except Exception:
            return False

    async def delete(self, *keys: str) -> None:
        if self.redis is None or not keys:
            return
        try:
            await self.redis.delete(*keys)
        except Exception:
            pass

    async def delete_prefix(self, prefix: str) -> None:
        if self.redis is None:
            return
        try:
            keys = await self.redis.keys(f"{prefix}*")
            if keys:
                await self.redis.delete(*keys)
        except Exception:
            pass

    async def get_json(self, key: str) -> Any | None:
        value = await self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None

    async def set_json(self, key: str, payload: Any, *, ttl_seconds: int) -> bool:
        try:
            serialized = json.dumps(payload, default=str)
        except (TypeError, ValueError):
            return False
        return await self.set(key, serialized, ttl_seconds=ttl_seconds)

    # ── sorted sets: trending & leaderboard structures ──

    async def zincr(self, key: str, member: str, amount: float = 1.0, *, ttl_seconds: int | None = None) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.zincrby(key, amount, member)
            if ttl_seconds:
                await self.redis.expire(key, ttl_seconds, nx=True)
        except Exception:
            pass

    async def ztop(self, key: str, *, limit: int = 10) -> list[tuple[str, float]]:
        if self.redis is None:
            return []
        try:
            rows = await self.redis.zrevrange(key, 0, limit - 1, withscores=True)
            return [(m, float(s)) for m, s in rows]
        except Exception:
            return []

    async def zscore(self, key: str, member: str) -> float | None:
        if self.redis is None:
            return None
        try:
            value = await self.redis.zscore(key, member)
            return float(value) if value is not None else None
        except Exception:
            return None
