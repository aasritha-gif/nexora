from __future__ import annotations

import asyncio
import logging

from app.core.config import Settings
from app.databases.base import DatabaseAdapter
from app.databases.monetdb import MonetDBAdapter
from app.databases.mongodb import MongoAdapter
from app.databases.neo4j import Neo4jAdapter
from app.databases.redis import RedisAdapter

log = logging.getLogger(__name__)


class Databases:
    """Owns the four database adapters and their lifecycle.

    Startup never fails because a database is down: the adapter is marked
    DEGRADED, dependent features report honest unavailability, and the rest
    of the platform keeps working.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.mongo = MongoAdapter(settings)
        self.redis = RedisAdapter(settings)
        self.neo4j = Neo4jAdapter(settings)
        self.monetdb = MonetDBAdapter(settings)
        self._adapters: list[DatabaseAdapter] = [
            self.mongo,
            self.redis,
            self.neo4j,
            self.monetdb,
        ]

    async def startup(self) -> None:
        results = await asyncio.gather(
            *(adapter.connect() for adapter in self._adapters),
            return_exceptions=True,
        )
        for adapter, result in zip(self._adapters, results):
            if isinstance(result, BaseException):
                adapter.mark_degraded(str(result) or result.__class__.__name__)
                log.error(
                    "Database degraded at startup: %s — %s",
                    adapter.name,
                    adapter.reason,
                    extra={"event": "database_degraded", "db": adapter.name},
                )
            else:
                log.info(
                    "Database connected: %s (%.0f ms)",
                    adapter.name,
                    adapter.latency_ms or 0,
                    extra={"event": "database_connected", "db": adapter.name},
                )

    async def shutdown(self) -> None:
        await asyncio.gather(
            *(adapter.close() for adapter in self._adapters),
            return_exceptions=True,
        )
        log.info("All database connections closed", extra={"event": "databases_closed"})

    async def refresh_health(self) -> None:
        await asyncio.gather(
            *(adapter.health_check() for adapter in self._adapters),
            return_exceptions=True,
        )

    def status(self) -> dict:
        return {
            "databases": [adapter.status_payload() for adapter in self._adapters],
            "summary": {
                "connected": sum(
                    1 for a in self._adapters if a.status.value == "connected"
                ),
                "total": len(self._adapters),
            },
        }
