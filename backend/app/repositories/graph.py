from __future__ import annotations

import logging

from neo4j.exceptions import Neo4jError

from app.core.errors import DatabaseUnavailableError
from app.databases.neo4j import Neo4jAdapter

log = logging.getLogger(__name__)


class GraphRepository:
    """Neo4j knowledge-graph access. All writes are idempotent (MERGE) so the
    ingestion pipeline and sync jobs can replay safely."""

    def __init__(self, adapter: Neo4jAdapter):
        self.adapter = adapter

    @property
    def available(self) -> bool:
        return self.adapter.available

    async def _run(self, query: str, params: dict | None = None):
        if not self.available:
            raise DatabaseUnavailableError("Neo4j")
        async with self.adapter.session() as session:
            return await session.run(query, parameters=params or {})

    async def _run_fetch(self, query: str, params: dict | None = None) -> list[dict]:
        if not self.available:
            raise DatabaseUnavailableError("Neo4j")
        async with self.adapter.session() as session:
            result = await session.run(query, parameters=params or {})
            return [record.data() async for record in result]

    # ── taxonomy ────────────────────────────────────────

    async def sync_department(self, code: str, name: str) -> None:
        await self._run(
            "MERGE (d:Department {code: $code}) SET d.name = $name",
            {"code": code, "name": name},
        )

    async def sync_subject(self, code: str, name: str, department_code: str) -> None:
        await self._run(
            """
            MERGE (s:Subject {code: $code})
            SET s.name = $name
            WITH s
            MATCH (d:Department {code: $dept})
            MERGE (d)-[:CONTAINS]->(s)
            """,
            {"code": code, "name": name, "dept": department_code},
        )

    async def sync_topic(self, code: str, name: str, subject_code: str) -> None:
        await self._run(
            """
            MERGE (t:Topic {code: $code})
            SET t.name = $name
            WITH t
            MATCH (s:Subject {code: $subject})
            MERGE (s)-[:HAS_TOPIC]->(t)
            """,
            {"code": code, "name": name, "subject": subject_code},
        )

    # ── resources & relationships ───────────────────────

    async def upsert_resource(
        self,
        *,
        resource_id: str,
        title: str,
        type: str,
        access: str,
        year: int | None,
        department_code: str | None,
        subject_codes: list[str],
        topic_codes: list[str],
        source_name: str | None,
    ) -> None:
        await self._run(
            """
            MERGE (r:Resource {resource_id: $rid})
            SET r.title = $title, r.type = $type, r.access = $access,
                r.year = $year
            WITH r
            OPTIONAL MATCH (src:Source {name: $source})
            FOREACH (_ IN CASE WHEN src IS NOT NULL THEN [1] ELSE [] END |
                MERGE (r)-[:DISCOVERED_FROM]->(src))
            WITH r
            FOREACH (code IN $subjects |
                MATCH (s:Subject {code: code})
                MERGE (s)-[:HAS_RESOURCE]->(r))
            WITH r
            FOREACH (code IN $topics |
                MATCH (t:Topic {code: code})
                MERGE (t)-[:HAS_RESOURCE]->(r))
            WITH r
            OPTIONAL MATCH (d:Department {code: $dept})
            FOREACH (_ IN CASE WHEN d IS NOT NULL THEN [1] ELSE [] END |
                MERGE (d)-[:HAS_RESOURCE]->(r))
            """,
            {
                "rid": resource_id, "title": title, "type": type, "access": access,
                "year": year, "subjects": subject_codes, "topics": topic_codes,
                "dept": department_code, "source": source_name,
            },
        )

    async def link_authors(self, resource_id: str, authors: list[str]) -> None:
        for author in authors:
            await self._run(
                """
                MERGE (a:Author {name: $author})
                WITH a
                MATCH (r:Resource {resource_id: $rid})
                MERGE (r)-[:WRITTEN_BY]->(a)
                """,
                {"author": author, "rid": resource_id},
            )

    async def ensure_source(self, name: str) -> None:
        await self._run("MERGE (s:Source {name: $name})", {"name": name})

    async def delete_resource(self, resource_id: str) -> None:
        await self._run(
            """
            MATCH (r:Resource {resource_id: $rid})
            OPTIONAL MATCH (r)-[rel]-()
            DELETE rel
            WITH r
            DELETE r
            """,
            {"rid": resource_id},
        )

    # ── users & activity ────────────────────────────────

    async def sync_user(
        self, *, user_id: str, department_code: str | None, role: str
    ) -> None:
        await self._run(
            """
            MERGE (u:User {user_id: $uid})
            SET u.role = $role
            WITH u
            OPTIONAL MATCH (d:Department {code: $dept})
            FOREACH (_ IN CASE WHEN d IS NOT NULL THEN [1] ELSE [] END |
                MERGE (u)-[:STUDIES]->(d))
            """,
            {"uid": user_id, "dept": department_code, "role": role},
        )

    async def record_activity(
        self, *, user_id: str, resource_id: str, relation: str
    ) -> None:
        if relation not in ("VIEWED", "BOOKMARKED", "RATED"):
            raise ValueError(f"Unsupported activity relation: {relation}")
        await self._run(
            f"""
            MATCH (u:User {{user_id: $uid}}), (r:Resource {{resource_id: $rid}})
            MERGE (u)-[:{relation}]->(r)
            """,
            {"uid": user_id, "rid": resource_id},
        )

    # ── queries ─────────────────────────────────────────

    async def related_resources(
        self, resource_id: str, *, limit: int = 8
    ) -> list[dict]:
        rows = await self._run_fetch(
            """
            MATCH (r:Resource {resource_id: $rid})-[:HAS_RESOURCE|HAS_TOPIC]-(t)
                  -[:HAS_RESOURCE]-(other:Resource)
            WHERE other.resource_id <> $rid
            WITH other, count(t) AS shared
            RETURN other.resource_id AS resource_id,
                   other.title AS title,
                   other.type AS type,
                   shared
            ORDER BY shared DESC
            LIMIT $limit
            """,
            {"rid": resource_id, "limit": limit},
        )
        return rows

    async def students_also_explored(
        self, resource_id: str, *, limit: int = 8
    ) -> list[dict]:
        rows = await self._run_fetch(
            """
            MATCH (u:User)-[:VIEWED|BOOKMARKED|RATED]->(r:Resource {resource_id: $rid})
            MATCH (u)-[:VIEWED|BOOKMARKED|RATED]->(other:Resource)
            WHERE other.resource_id <> $rid
            WITH other, count(DISTINCT u) AS co_viewers
            RETURN other.resource_id AS resource_id, co_viewers
            ORDER BY co_viewers DESC
            LIMIT $limit
            """,
            {"rid": resource_id, "limit": limit},
        )
        return rows

    async def because_you_read(
        self, user_id: str, *, limit: int = 8
    ) -> list[dict]:
        """Resources sharing topics with what the user actually read."""
        rows = await self._run_fetch(
            """
            MATCH (u:User {user_id: $uid})-[:VIEWED|BOOKMARKED]->(seed:Resource)
            MATCH (seed)-[:HAS_RESOURCE|HAS_TOPIC]-(t)-[:HAS_RESOURCE]-(other:Resource)
            WHERE other.resource_id <> seed.resource_id
            WITH other, count(DISTINCT t) AS shared, count(DISTINCT seed) AS seeds
            RETURN other.resource_id AS resource_id, shared, seeds
            ORDER BY seeds DESC, shared DESC
            LIMIT $limit
            """,
            {"uid": user_id, "limit": limit},
        )
        return rows

    async def department_graph(self) -> list[dict]:
        rows = await self._run_fetch(
            """
            MATCH (d:Department)-[:CONTAINS]->(s:Subject)-[:HAS_TOPIC]->(t:Topic)
            RETURN d.code AS department, d.name AS department_name,
                   s.code AS subject, s.name AS subject_name,
                   collect(t.name)[..6] AS topics,
                   count {(s)-[:HAS_RESOURCE]->()} AS resource_count
            ORDER BY department_name, subject_name
            """
        )
        return rows

    async def trending_topics(self, *, days: int = 30, limit: int = 10) -> list[dict]:
        rows = await self._run_fetch(
            """
            MATCH (t:Topic)
            OPTIONAL MATCH (:User)-[v:VIEWED]->(:Resource)-[:HAS_RESOURCE|HAS_TOPIC]-(t)
            RETURN t.name AS topic, t.code AS code, count(v) AS views
            ORDER BY views DESC, t.name
            LIMIT $limit
            """,
            {"limit": limit},
        )
        return rows

    async def authors_with_works(self, *, name_contains: str = "", limit: int = 40) -> list[dict]:
        query = """
            MATCH (a:Author)<-[:WRITTEN_BY]-(r:Resource)
            WHERE a.name CONTAINS $needle
            RETURN a.name AS name, count(r) AS works,
                   collect(r.title)[..3] AS sample_titles
            ORDER BY works DESC
            LIMIT $limit
        """
        return await self._run_fetch(
            query, {"needle": name_contains, "limit": limit}
        )
