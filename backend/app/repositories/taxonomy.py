from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.errors import ConflictError, NotFoundError
from app.models.taxonomy import Department, Subject, Topic


class TaxonomyRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.departments = db.departments
        self.subjects = db.subjects
        self.topics = db.topics

    # ── departments ─────────────────────────────────────

    async def upsert_department(self, dept: Department) -> Department:
        await self.departments.update_one(
            {"code": dept.code.upper()}, {"$set": dept.model_dump()}, upsert=True
        )
        return dept

    async def list_departments(self, *, active_only: bool = True) -> list[Department]:
        query = {"is_active": True} if active_only else {}
        cursor = self.departments.find(query).sort("sort_order", 1)
        return [Department(**doc) async for doc in cursor]

    async def get_department(self, code: str) -> Department:
        doc = await self.departments.find_one({"code": code.upper()})
        if not doc:
            raise NotFoundError(f"Department '{code}' not found")
        return Department(**doc)

    async def department_exists(self, code: str) -> bool:
        return await self.departments.find_one({"code": code.upper()}, {"_id": 1}) is not None

    async def update_department(self, code: str, fields: dict) -> Department:
        allowed = {k: v for k, v in fields.items() if k in {
            "name", "description", "is_active", "sort_order", "icon", "color"
        }}
        doc = await self.departments.find_one_and_update(
            {"code": code.upper()}, {"$set": allowed}, return_document=True
        )
        if not doc:
            raise NotFoundError(f"Department '{code}' not found")
        return Department(**doc)

    # ── subjects ────────────────────────────────────────

    async def upsert_subject(self, subject: Subject) -> Subject:
        if not await self.department_exists(subject.department_code):
            raise NotFoundError(f"Department '{subject.department_code}' not found")
        existing = await self.subjects.find_one({"code": subject.code})
        if existing and existing["department_code"] != subject.department_code:
            raise ConflictError("Subject code already used in another department")
        await self.subjects.update_one(
            {"code": subject.code}, {"$set": subject.model_dump()}, upsert=True
        )
        return subject

    async def list_subjects(self, department_code: str | None = None) -> list[Subject]:
        query = {"department_code": department_code.upper()} if department_code else {}
        cursor = self.subjects.find(query).sort("name", 1)
        return [Subject(**doc) async for doc in cursor]

    async def get_subject(self, code: str) -> Subject:
        doc = await self.subjects.find_one({"code": code})
        if not doc:
            raise NotFoundError(f"Subject '{code}' not found")
        return Subject(**doc)

    async def subject_exists(self, code: str) -> bool:
        return await self.subjects.find_one({"code": code}, {"_id": 1}) is not None

    # ── topics ──────────────────────────────────────────

    async def upsert_topic(self, topic: Topic) -> Topic:
        if not await self.subject_exists(topic.subject_code):
            raise NotFoundError(f"Subject '{topic.subject_code}' not found")
        await self.topics.update_one(
            {"code": topic.code}, {"$set": topic.model_dump()}, upsert=True
        )
        return topic

    async def list_topics(self, subject_code: str | None = None) -> list[Topic]:
        query = {"subject_code": subject_code} if subject_code else {}
        cursor = self.topics.find(query).sort("name", 1)
        return [Topic(**doc) async for doc in cursor]

    async def get_topic(self, code: str) -> Topic:
        doc = await self.topics.find_one({"code": code})
        if not doc:
            raise NotFoundError(f"Topic '{code}' not found")
        return Topic(**doc)

    async def topic_exists(self, code: str) -> bool:
        return await self.topics.find_one({"code": code}, {"_id": 1}) is not None

    # ── name maps (hydration) ───────────────────────────

    async def name_maps(self) -> dict[str, dict[str, str]]:
        departments: dict[str, str] = {}
        subjects: dict[str, str] = {}
        topics: dict[str, str] = {}
        async for doc in self.departments.find({}, {"code": 1, "name": 1}):
            departments[doc["code"]] = doc["name"]
        async for doc in self.subjects.find({}, {"code": 1, "name": 1}):
            subjects[doc["code"]] = doc["name"]
        async for doc in self.topics.find({}, {"code": 1, "name": 1}):
            topics[doc["code"]] = doc["name"]
        return {"department": departments, "subject": subjects, "topic": topics}

    # ── seeding ─────────────────────────────────────────

    async def is_empty(self) -> bool:
        return await self.departments.count_documents({}) == 0

    async def seed(
        self,
        departments: list[Department],
        subjects: list[Subject],
        topics: list[Topic],
    ) -> None:
        if departments:
            await self.departments.insert_many([d.model_dump() for d in departments])
        if subjects:
            await self.subjects.insert_many([s.model_dump() for s in subjects])
        if topics:
            await self.topics.insert_many([t.model_dump() for t in topics])
