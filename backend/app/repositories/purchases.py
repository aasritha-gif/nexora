from __future__ import annotations

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.core.errors import NotFoundError
from app.models.purchase import Purchase
from app.repositories.counters import next_id


class PurchaseRepository:
    """Premium entitlements. A resource is accessible when a `paid` purchase
    row exists for (user, resource). Nothing else grants premium access."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.purchases

    async def has_access(self, user_id: str, resource_id: str) -> bool:
        doc = await self.collection.find_one(
            {"user_id": user_id, "resource_id": resource_id, "status": "paid"},
            {"_id": 1},
        )
        return doc is not None

    async def create_pending(
        self, *, user_id: str, resource_id: str, amount_usd: float, provider: str
    ) -> Purchase:
        existing = await self.collection.find_one(
            {"user_id": user_id, "resource_id": resource_id, "status": "pending"},
            {"_id": 0},
        )
        if existing:
            return Purchase(**existing)
        purchase = Purchase(
            purchase_id=await next_id(self.db, "purchase"),
            user_id=user_id,
            resource_id=resource_id,
            amount_usd=amount_usd,
            provider=provider,
        )
        await self.collection.insert_one(purchase.model_dump())
        return purchase

    async def attach_reference(self, purchase_id: str, reference: str) -> None:
        await self.collection.update_one(
            {"purchase_id": purchase_id},
            {"$set": {"provider_reference": reference}},
        )

    async def get_by_reference(self, provider: str, reference: str) -> Purchase | None:
        doc = await self.collection.find_one(
            {"provider": provider, "provider_reference": reference}, {"_id": 0}
        )
        return Purchase(**doc) if doc else None

    async def get(self, purchase_id: str) -> Purchase | None:
        doc = await self.collection.find_one({"purchase_id": purchase_id}, {"_id": 0})
        return Purchase(**doc) if doc else None

    async def mark_paid(self, purchase_id: str) -> Purchase:
        doc = await self.collection.find_one_and_update(
            {"purchase_id": purchase_id},
            {"$set": {"status": "paid", "paid_at": datetime.now(timezone.utc)}},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            raise NotFoundError("Purchase not found")
        doc.pop("_id", None)
        return Purchase(**doc)

    async def mark_refunded(self, purchase_id: str) -> Purchase:
        doc = await self.collection.find_one_and_update(
            {"purchase_id": purchase_id},
            {"$set": {"status": "refunded"}},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            raise NotFoundError("Purchase not found")
        doc.pop("_id", None)
        return Purchase(**doc)

    async def list_for_user(self, user_id: str) -> list[Purchase]:
        cursor = self.collection.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1)
        return [Purchase(**doc) async for doc in cursor]
