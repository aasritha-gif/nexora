from __future__ import annotations

import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.core.errors import ConflictError, NotFoundError
from app.models.engagement import ReadingHistoryEntry, Review
from app.repositories.counters import next_id


class BookmarkRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.bookmarks

    async def add(self, user_id: str, resource_id: str) -> bool:
        try:
            await self.collection.insert_one(
                {"user_id": user_id, "resource_id": resource_id,
                 "created_at": datetime.now(timezone.utc)}
            )
            return True
        except Exception:
            return False  # duplicate bookmark — idempotent

    async def remove(self, user_id: str, resource_id: str) -> bool:
        result = await self.collection.delete_one(
            {"user_id": user_id, "resource_id": resource_id}
        )
        return result.deleted_count > 0

    async def is_bookmarked(self, user_id: str, resource_id: str) -> bool:
        return await self.collection.find_one(
            {"user_id": user_id, "resource_id": resource_id}, {"_id": 1}
        ) is not None

    async def user_bookmarks(self, user_id: str) -> list[dict]:
        cursor = self.collection.find({"user_id": user_id}).sort("created_at", -1)
        return [
            {"resource_id": doc["resource_id"], "created_at": doc["created_at"]}
            async for doc in cursor
        ]

    async def count_for_resource(self, resource_id: str) -> int:
        return await self.collection.count_documents({"resource_id": resource_id})


class ReadingHistoryRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.reading_history

    async def record_view(self, user_id: str, resource_id: str) -> ReadingHistoryEntry:
        now = datetime.now(timezone.utc)
        doc = await self.collection.find_one_and_update(
            {"user_id": user_id, "resource_id": resource_id},
            {
                "$set": {"last_viewed_at": now},
                "$setOnInsert": {"first_viewed_at": now,
                                 "progress": {"percent": 0, "last_chunk": 0, "completed": False}},
                "$inc": {"view_count": 1},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return ReadingHistoryEntry(**doc)

    async def update_progress(
        self, user_id: str, resource_id: str, *, percent: int, last_chunk: int
    ) -> ReadingHistoryEntry:
        doc = await self.collection.find_one_and_update(
            {"user_id": user_id, "resource_id": resource_id},
            {
                "$set": {
                    "progress.percent": percent,
                    "progress.last_chunk": last_chunk,
                    "progress.completed": percent >= 100,
                    "last_viewed_at": datetime.now(timezone.utc),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            raise NotFoundError("No reading history for this resource")
        return ReadingHistoryEntry(**doc)

    async def user_history(self, user_id: str, *, limit: int = 50) -> list[ReadingHistoryEntry]:
        cursor = (
            self.collection.find({"user_id": user_id})
            .sort("last_viewed_at", -1)
            .limit(limit)
        )
        return [ReadingHistoryEntry(**doc) async for doc in cursor]

    async def in_progress(self, user_id: str, *, limit: int = 12) -> list[ReadingHistoryEntry]:
        cursor = (
            self.collection.find({
                "user_id": user_id,
                "progress.completed": False,
                "progress.percent": {"$gt": 0},
            })
            .sort("last_viewed_at", -1)
            .limit(limit)
        )
        return [ReadingHistoryEntry(**doc) async for doc in cursor]

    async def completed(self, user_id: str) -> list[ReadingHistoryEntry]:
        cursor = self.collection.find({
            "user_id": user_id, "progress.completed": True,
        }).sort("last_viewed_at", -1)
        return [ReadingHistoryEntry(**doc) async for doc in cursor]


class ReviewRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.reviews

    async def upsert(self, user_id: str, resource_id: str, *, rating: int, title: str | None, body: str) -> Review:
        existing = await self.collection.find_one(
            {"user_id": user_id, "resource_id": resource_id}
        )
        if existing:
            doc = await self.collection.find_one_and_update(
                {"user_id": user_id, "resource_id": resource_id},
                {"$set": {
                    "rating": rating, "title": title, "body": body,
                    "updated_at": datetime.now(timezone.utc),
                }},
                return_document=ReturnDocument.AFTER,
            )
            return Review(**doc)
        review_id = await next_id(self.db, "review")
        review = Review(
            review_id=review_id,
            user_id=user_id,
            resource_id=resource_id,
            rating=rating,
            title=title,
            body=body,
        )
        try:
            await self.collection.insert_one(review.model_dump())
        except Exception as exc:
            raise ConflictError("Review already exists") from exc
        return review

    async def list_for_resource(self, resource_id: str, *, include_hidden: bool = False) -> list[Review]:
        query: dict = {"resource_id": resource_id}
        if not include_hidden:
            query["status"] = "published"
        cursor = self.collection.find(query).sort("created_at", -1)
        return [Review(**doc) async for doc in cursor]

    async def flag(self, review_id: str) -> Review:
        doc = await self.collection.find_one_and_update(
            {"review_id": review_id},
            {"$set": {"status": "flagged"}},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            raise NotFoundError("Review not found")
        return Review(**doc)

    async def moderate(self, review_id: str, *, remove: bool, reason: str | None) -> Review:
        doc = await self.collection.find_one_and_update(
            {"review_id": review_id},
            {"$set": {
                "status": "removed" if remove else "published",
                "moderated_reason": reason if remove else None,
            }},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            raise NotFoundError("Review not found")
        return Review(**doc)

    async def flagged(self) -> list[Review]:
        cursor = self.collection.find({"status": "flagged"}).sort("created_at", -1)
        return [Review(**doc) async for doc in cursor]

    async def refresh_resource_rating(self, resource_id: str) -> tuple[int, int]:
        pipeline = [
            {"$match": {"resource_id": resource_id, "status": "published"}},
            {"$group": {"_id": None, "sum": {"$sum": "$rating"}, "count": {"$sum": 1}}},
        ]
        docs = [doc async for doc in self.collection.aggregate(pipeline)]
        if docs:
            rating_sum, count = docs[0]["sum"], docs[0]["count"]
        else:
            rating_sum, count = 0, 0
        await self.db.resources.update_one(
            {"resource_id": resource_id},
            {"$set": {"stats.rating_sum": rating_sum, "stats.rating_count": count}},
        )
        return rating_sum, count

    async def delete_for_user(self, user_id: str, resource_id: str) -> bool:
        result = await self.collection.delete_one(
            {"user_id": user_id, "resource_id": resource_id}
        )
        return result.deleted_count > 0


def new_object_id() -> str:
    return uuid.uuid4().hex
