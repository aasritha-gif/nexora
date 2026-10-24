from __future__ import annotations

import logging
import time

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.core.config import Settings
from app.databases.base import DatabaseAdapter

log = logging.getLogger(__name__)

CONSTRAINTS = [
    "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
    "CREATE CONSTRAINT resource_id IF NOT EXISTS FOR (r:Resource) REQUIRE r.resource_id IS UNIQUE",
    "CREATE CONSTRAINT dept_code IF NOT EXISTS FOR (d:Department) REQUIRE d.code IS UNIQUE",
    "CREATE CONSTRAINT subject_code IF NOT EXISTS FOR (s:Subject) REQUIRE s.code IS UNIQUE",
    "CREATE CONSTRAINT topic_code IF NOT EXISTS FOR (t:Topic) REQUIRE t.code IS UNIQUE",
    "CREATE CONSTRAINT author_name IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
    "CREATE CONSTRAINT source_name IF NOT EXISTS FOR (s:Source) REQUIRE s.name IS UNIQUE",
]


class Neo4jAdapter(DatabaseAdapter):
    """Neo4j — the knowledge graph: taxonomy, relationships, co-activity."""

    name = "Neo4j"

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.driver: AsyncDriver | None = None

    async def connect(self) -> None:
        started = time.monotonic()
        driver = AsyncGraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password),
            connection_timeout=6,
        )
        await driver.verify_connectivity()
        self.driver = driver
        await self._ensure_constraints()
        self._mark_connected((time.monotonic() - started) * 1000)

    async def close(self) -> None:
        if self.driver is not None:
            await self.driver.close()
            self.driver = None

    async def ping(self) -> None:
        assert self.driver is not None, "Neo4j adapter not connected"
        await self.driver.verify_connectivity()

    async def session(self):
        assert self.driver is not None, "Neo4j adapter not connected"
        return self.driver.session()

    async def _ensure_constraints(self) -> None:
        assert self.driver is not None
        try:
            async with self.driver.session() as session:
                for statement in CONSTRAINTS:
                    await session.run(statement)
            log.info("Neo4j constraints ensured", extra={"event": "neo4j_constraints"})
        except Exception as exc:  # constraints are best-effort; queries still work
            log.warning(
                "Neo4j constraint creation failed: %s",
                exc,
                extra={"event": "neo4j_constraints_failed"},
            )
