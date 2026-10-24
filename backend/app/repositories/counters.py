from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

_ID_PREFIXES = {
    "resource": "RES",
    "user": "USR",
    "review": "REV",
    "note": "NTE",
    "flashcard": "FLC",
    "question": "QST",
    "run": "RUN",
    "message": "MSG",
    "purchase": "PUR",
}


async def next_id(db: AsyncIOMotorDatabase, kind: str) -> str:
    """Monotonic human-readable IDs: RES-000001, USR-000042, ..."""
    doc = await db.counters.find_one_and_update(
        {"_id": kind},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    prefix = _ID_PREFIXES.get(kind, kind.upper()[:3])
    return f"{prefix}-{doc['seq']:06d}"
