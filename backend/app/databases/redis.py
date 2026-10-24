from __future__ import annotations

import logging
import time

import redis.asyncio as aioredis

from app.core.config import Settings
from app.databases.base import DatabaseAdapter

log = logging.getLogger(__name__)


class RedisAdapter(DatabaseAdapter):
    """Redis — cache, sessions, trending, rate limiting, temporary state."""

    name = "Redis"

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.client: aioredis.Redis | None = None

    async def connect(self) -> None:
        started = time.monotonic()
        client = aioredis.from_url(
            self.settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        await client.ping()
        self.client = client
        self._mark_connected((time.monotonic() - started) * 1000)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def ping(self) -> None:
        assert self.client is not None, "Redis adapter not connected"
        await self.client.ping()
