from __future__ import annotations

import logging
import time

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import Settings
from app.databases.base import DatabaseAdapter

log = logging.getLogger(__name__)

CONNECT_TIMEOUT_MS = 6000


class MongoAdapter(DatabaseAdapter):
    """MongoDB — canonical application/document store."""

    name = "MongoDB"

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.client: AsyncIOMotorClient | None = None
        self.db: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        started = time.monotonic()
        client = AsyncIOMotorClient(
            self.settings.mongo_url,
            serverSelectionTimeoutMS=CONNECT_TIMEOUT_MS,
            connectTimeoutMS=CONNECT_TIMEOUT_MS,
        )
        await client.admin.command("ping")
        self.client = client
        self.db = client[self.settings.mongo_db]
        await self._ensure_indexes()
        self._mark_connected((time.monotonic() - started) * 1000)

    async def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None
            self.db = None

    async def ping(self) -> None:
        if self.client is None:
            # Boot happened while MongoDB was down: a later health probe is the
            # retry point, so the process recovers without a restart.
            await self.connect()
            return
        await self.client.admin.command("ping")

    async def _ensure_indexes(self) -> None:
        assert self.db is not None
        db = self.db
        await db.users.create_index("email", unique=True)
        await db.users.create_index("student_id", unique=True, sparse=True)
        await db.users.create_index("user_id", unique=True)
        # Code uniqueness is what makes the taxonomy upserts and the bulk seed
        # insert safe to run repeatedly.
        await db.departments.create_index("code", unique=True)
        await db.subjects.create_index("code", unique=True)
        await db.subjects.create_index("department_code")
        await db.topics.create_index("code", unique=True)
        await db.topics.create_index("subject_code")
        await db.resources.create_index("resource_id", unique=True)
        # Drop then recreate identifier indexes so sparse=True is always applied
        # even when a previous (non-sparse) index already exists in the collection.
        for _idx in ("identifiers.doi_1", "identifiers.isbn_1",
                     "identifiers.arxiv_id_1", "identifiers.source_id_1"):
            try:
                await db.resources.drop_index(_idx)
            except Exception:
                pass  # index didn't exist — fine
        await db.resources.create_index("identifiers.doi", unique=True, sparse=True)
        await db.resources.create_index("identifiers.isbn", unique=True, sparse=True)
        await db.resources.create_index("identifiers.arxiv_id", unique=True, sparse=True)
        await db.resources.create_index("identifiers.source_id", unique=True, sparse=True)
        await db.resources.create_index("fingerprint")
        await db.resources.create_index("type")
        await db.resources.create_index("taxonomy.department_code")
        await db.resources.create_index("taxonomy.subject_codes")
        await db.resources.create_index("taxonomy.topic_codes")
        await db.resources.create_index("created_at")
        await db.resources.create_index(
            [
                ("title", "text"),
                ("description", "text"),
                ("keywords", "text"),
                ("authors", "text"),
            ],
            name="resource_text",
            weights={"title": 10, "keywords": 5, "description": 3, "authors": 4},
            default_language="english",
        )
        await db.bookmarks.create_index(
            [("user_id", 1), ("resource_id", 1)], unique=True
        )
        await db.reading_history.create_index(
            [("user_id", 1), ("resource_id", 1)], unique=True
        )
        await db.reviews.create_index(
            [("user_id", 1), ("resource_id", 1)], unique=True
        )
        await db.reviews.create_index("resource_id")
        await db.chat_messages.create_index(
            [("resource_id", 1), ("user_id", 1), ("created_at", 1)]
        )
        await db.user_notes.create_index([("user_id", 1), ("resource_id", 1)])
        await db.user_flashcards.create_index([("user_id", 1), ("resource_id", 1)])
        await db.resource_chunks.create_index(
            [("resource_id", 1), ("chunk_index", 1)], unique=True
        )
        await db.ai_overviews.create_index("resource_id", unique=True)
        await db.sessions.create_index("expireAt", expireAfterSeconds=0)
        await db.sessions.create_index(
            [("user_id", 1), ("jti", 1)], unique=True
        )
        await db.purchases.create_index(
            [("user_id", 1), ("status", 1)]
        )
        await db.purchases.create_index(
            [("provider", 1), ("provider_reference", 1)], sparse=True
        )
        await db.bookmarks.create_index("created_at")
        await db.reading_history.create_index("created_at")
        await db.resources.create_index(
            [("stats.views", -1), ("stats.reads", -1)]
        )
        await db.resources.create_index(
            [("stats.rating_score", -1), ("stats.rating_count", -1)]
        )
        await db.resources.create_index([("access", 1), ("created_at", -1)])
        await db.ingestion_runs.create_index("created_at")
        await db.ingestion_retry_queue.create_index("next_attempt_at")
        await db.analytics_outbox.create_index("created_at")
        await db.password_resets.create_index("expires_at", expireAfterSeconds=0)
        await db.sources.create_index("source_key", unique=True)
        log.info("MongoDB indexes ensured", extra={"event": "mongo_indexes", "db": "MongoDB"})
