from __future__ import annotations

import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.errors import ConflictError, NotFoundError
from app.models.resource import Resource
from app.repositories.counters import next_id
from app.schemas.search import SearchFilters

log = logging.getLogger(__name__)

CANDIDATE_LIMIT = 400


class ResourceRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.resources

    # ── writes ──────────────────────────────────────────

    async def insert(self, resource: Resource) -> Resource:
        try:
            await self.collection.insert_one(resource.model_dump(exclude_none=True))
        except DuplicateKeyError as exc:
            raise ConflictError(
                "Resource with identical identifier already exists",
                code="duplicate_resource",
            ) from exc
        return resource

    async def new_resource_id(self) -> str:
        return await next_id(self.db, "resource")

    async def update_fields(self, resource_id: str, fields: dict) -> Resource | None:
        from datetime import datetime, timezone

        # Flatten the fields dict into dot-notation paths so we can separate
        # None values (→ $unset, field becomes absent) from real values (→ $set).
        # Absent fields are skipped by sparse unique indexes; explicit nulls are not.
        def _flatten(d: dict, prefix: str = "") -> tuple[dict, list[str]]:
            set_ops: dict = {}
            unset_keys: list[str] = []
            for k, v in d.items():
                path = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
                if isinstance(v, dict):
                    s, u = _flatten(v, path)
                    set_ops.update(s)
                    unset_keys.extend(u)
                elif v is None:
                    unset_keys.append(path)
                else:
                    set_ops[path] = v
            return set_ops, unset_keys

        set_fields, unset_keys = _flatten(fields)
        set_fields["updated_at"] = datetime.now(timezone.utc)

        update: dict = {"$set": set_fields}
        if unset_keys:
            update["$unset"] = {k: "" for k in unset_keys}

        doc = await self.collection.find_one_and_update(
            {"resource_id": resource_id},
            update,
            return_document=ReturnDocument.AFTER,
        )
        return Resource(**doc) if doc else None

    async def inc_stat(self, resource_id: str, field: str, amount: int = 1) -> None:
        await self.collection.update_one(
            {"resource_id": resource_id},
            {"$inc": {f"stats.{field}": amount}, "$set": {"updated_at": _now()}},
        )

    async def delete(self, resource_id: str) -> None:
        result = await self.collection.delete_one({"resource_id": resource_id})
        if result.deleted_count == 0:
            raise NotFoundError("Resource not found")
        await self.db.reviews.delete_many({"resource_id": resource_id})
        await self.db.bookmarks.delete_many({"resource_id": resource_id})
        await self.db.reading_history.delete_many({"resource_id": resource_id})
        await self.db.resource_chunks.delete_many({"resource_id": resource_id})
        await self.db.chat_messages.delete_many({"resource_id": resource_id})
        await self.db.ai_overviews.delete_one({"resource_id": resource_id})
        log.info("Resource deleted", extra={"event": "resource_deleted", "resource_id": resource_id})

    # ── reads ───────────────────────────────────────────

    async def get(self, resource_id: str) -> Resource:
        doc = await self.collection.find_one({"resource_id": resource_id})
        if not doc:
            raise NotFoundError("Resource not found")
        return Resource(**doc)

    async def get_many(self, resource_ids: list[str]) -> list[Resource]:
        if not resource_ids:
            return []
        cursor = self.collection.find({"resource_id": {"$in": resource_ids}})
        return [Resource(**doc) async for doc in cursor]

    async def find_by_identifier(self, *, kind: str, value: str) -> Resource | None:
        """kind: doi | isbn | arxiv_id | source_id | url"""
        doc = await self.collection.find_one({f"identifiers.{kind}": value})
        return Resource(**doc) if doc else None

    async def find_by_fingerprint(self, fingerprint: str) -> Resource | None:
        doc = await self.collection.find_one({"fingerprint": fingerprint})
        return Resource(**doc) if doc else None

    async def exists(self, resource_id: str) -> bool:
        return await self.collection.find_one({"resource_id": resource_id}, {"_id": 1}) is not None

    # ── queries ─────────────────────────────────────────

    @staticmethod
    def build_query(filters: SearchFilters) -> dict:
        query: dict[str, Any] = {}
        if filters.department:
            dept = filters.department.strip()
            if dept.upper() in ("CS", "CSE"):
                query["taxonomy.department_code"] = {"$in": ["CSE", "CS"]}
            elif dept.upper() in ("EC", "ECE"):
                query["taxonomy.department_code"] = {"$in": ["ECE", "EC"]}
            elif dept.upper() in ("EE", "EEE"):
                query["taxonomy.department_code"] = {"$in": ["EEE", "EE"]}
            elif dept.upper() in ("ME", "MECH"):
                query["taxonomy.department_code"] = {"$in": ["MECH", "ME"]}
            else:
                query["taxonomy.department_code"] = dept
        if filters.subject:
            query["taxonomy.subject_codes"] = filters.subject
        if filters.topic:
            query["taxonomy.topic_codes"] = filters.topic
        if filters.types:
            query["type"] = {"$in": [t.value for t in filters.types]}
        if filters.year_from or filters.year_to:
            year: dict[str, int] = {}
            if filters.year_from:
                year["$gte"] = filters.year_from
            if filters.year_to:
                year["$lte"] = filters.year_to
            query["year"] = year
        if filters.difficulty:
            query["classification.difficulty"] = filters.difficulty.value
        if filters.access:
            query["access"] = filters.access.value
        if filters.author:
            query["authors"] = {"$regex": _escape(filters.author), "$options": "i"}
        if filters.min_rating:
            query["stats.rating_count"] = {"$gt": 0}
        return query

    async def query(
        self,
        filters: SearchFilters,
        *,
        skip: int = 0,
        limit: int = 20,
        sort: list[tuple[str, int]] | None = None,
    ) -> tuple[list[Resource], int]:
        query = self.build_query(filters)
        total = await self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort(sort or [("created_at", -1)])
            .skip(skip)
            .limit(limit)
        )
        return [Resource(**doc) async for doc in cursor], total

    async def text_candidates(
        self, filters: SearchFilters, *, limit: int = CANDIDATE_LIMIT
    ) -> list[tuple[Resource, float]]:
        """Full-text candidates (MongoDB $text) with relevance scores."""
        query = self.build_query(filters)
        terms = " ".join(filters.query.split())
        if not terms:
            return []
        text_clause = {"$text": {"$search": terms}}
        final_query = {"$and": [query, text_clause]} if query else text_clause
        cursor = self.collection.find(
            final_query, {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        results = []
        async for doc in cursor:
            score = doc.pop("score", 0.0)
            results.append((Resource(**doc), float(score)))
        return results

    async def recent(
        self, *, limit: int = 12, types: list[str] | None = None,
        department: str | None = None,
    ) -> list[Resource]:
        query: dict[str, Any] = {}
        if types:
            query["type"] = {"$in": types}
        if department:
            query["taxonomy.department_code"] = department
        cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
        return [Resource(**doc) async for doc in cursor]

    async def popular(self, *, limit: int = 12, department: str | None = None) -> list[Resource]:
        query: dict[str, Any] = {}
        if department:
            query["taxonomy.department_code"] = department
        cursor = (
            self.collection.find(query)
            .sort([("stats.views", -1), ("stats.reads", -1)])
            .limit(limit)
        )
        return [Resource(**doc) async for doc in cursor]

    async def by_ids_ordered(self, ids: list[str]) -> list[Resource]:
        found = await self.get_many(ids)
        by_id = {r.resource_id: r for r in found}
        return [by_id[i] for i in ids if i in by_id]

    # ── aggregates ──────────────────────────────────────

    async def count(self, *, department: str | None = None) -> int:
        query = {"taxonomy.department_code": department} if department else {}
        return await self.collection.count_documents(query)

    async def counts_by_department(self) -> dict[str, int]:
        pipeline = [
            {"$match": {"taxonomy.department_code": {"$ne": None}}},
            {"$group": {"_id": "$taxonomy.department_code", "count": {"$sum": 1}}},
        ]
        return {
            doc["_id"]: doc["count"] async for doc in self.collection.aggregate(pipeline)
        }

    async def counts_by_type(self) -> dict[str, int]:
        pipeline = [{"$group": {"_id": "$type", "count": {"$sum": 1}}}]
        return {doc["_id"]: doc["count"] async for doc in self.collection.aggregate(pipeline)}

    async def counts_by_subject(self, department_code: str) -> dict[str, int]:
        pipeline = [
            {"$match": {"taxonomy.department_code": department_code}},
            {"$unwind": "$taxonomy.subject_codes"},
            {"$group": {"_id": "$taxonomy.subject_codes", "count": {"$sum": 1}}},
        ]
        return {
            doc["_id"]: doc["count"] async for doc in self.collection.aggregate(pipeline)
        }

    async def counts_by_topic(self, subject_code: str) -> dict[str, int]:
        pipeline = [
            {"$match": {"taxonomy.subject_codes": subject_code}},
            {"$unwind": "$taxonomy.topic_codes"},
            {"$group": {"_id": "$taxonomy.topic_codes", "count": {"$sum": 1}}},
        ]
        return {
            doc["_id"]: doc["count"] async for doc in self.collection.aggregate(pipeline)
        }

    async def trending_topics(self, department_code: str, *, limit: int = 5) -> list[str]:
        pipeline = [
            {"$match": {"taxonomy.department_code": department_code}},
            {"$unwind": "$taxonomy.topic_codes"},
            {"$group": {
                "_id": "$taxonomy.topic_codes",
                "score": {"$sum": {"$add": ["$stats.views", {"$multiply": ["$stats.reads", 2]}]}},
            }},
            {"$sort": {"score": -1}},
            {"$limit": limit},
        ]
        return [doc["_id"] async for doc in self.collection.aggregate(pipeline)]

    async def seed_count(self) -> int:
        return await self.collection.count_documents({"flags.is_seed_data": True})

    async def author_list(self, *, limit: int = 50) -> list[dict]:
        pipeline = [
            {"$unwind": "$authors"},
            {"$group": {"_id": "$authors", "works": {"$sum": 1}}},
            {"$sort": {"works": -1}},
            {"$limit": limit},
        ]
        return [dict(name=doc["_id"], works=doc["works"]) async for doc in self.collection.aggregate(pipeline)]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("$", "\\$").replace("^", "\\^")


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
