"""Turns the static seed data into documents across all four databases.

Three guarantees the CLI and the admin endpoints rely on:

* **Idempotent.** Re-running never duplicates: taxonomy upserts on `code`, demo
  resources are found by their stable `source_id`, reviews upsert per
  (user, resource), and counters are *recomputed* from the collections rather
  than incremented.
* **Degradation-tolerant.** Neo4j and MonetDB being down produces a warning on
  the report, not a failed seed — MongoDB is the only hard requirement.
* **Reversible.** Every demo document carries a marker
  (`flags.is_seed_data` / a `DEMO-` student ID) that `purge_demo` uses to
  remove it from all four stores. Taxonomy is reference data and is never
  purged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.core.security import hash_password
from app.databases.monetdb import sql_lit, validate_code, validate_event_type, validate_id
from app.ingestion.dedup import fingerprint
from app.ingestion.sources.base import DiscoveredItem
from app.models.resource import (
    Resource,
    ResourceClassification,
    ResourceFlags,
    ResourceIdentifiers,
    ResourceSource,
    ResourceTaxonomy,
)
from app.models.user import Role, User
from app.seed.demo_data import (
    DEMO_ENGAGEMENT,
    DEMO_PASSWORD,
    DEMO_RESOURCES,
    DEMO_REVIEWS,
    DEMO_SOURCE_LICENSE,
    DEMO_SOURCE_NAME,
    DEMO_USERS,
    SEED_LABEL,
)
from app.seed.taxonomy_data import build_departments, build_subjects, build_topics

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from app.api.dependencies import AppState

logger = get_logger("nexora.seed")

# Prefixed the same way `IngestionService._normalize` prefixes real adapters, so
# demo resources collide with nothing and `purge_demo` can find them by ID.
DEMO_SOURCE_ID_PREFIX = "nexora-demo"

# Demo analytics are spread across this window so the dashboard has a shape.
ANALYTICS_WINDOW_DAYS = 14

# Collections keyed by resource_id that must not outlive a purged demo resource.
_RESOURCE_DEPENDENTS = (
    "reviews",
    "bookmarks",
    "reading_history",
    "resource_chunks",
    "chat_messages",
    "ai_overviews",
)

_DEMO_STUDENT_ID_PREFIX = "DEMO-"


@dataclass
class SeedReport:
    """What a seed run touched. Rendered by `scripts/seed.py` and the admin API."""

    departments: int = 0
    subjects: int = 0
    topics: int = 0
    graph_taxonomy_nodes: int = 0
    graph_resources: int = 0
    users_created: int = 0
    users_existing: int = 0
    resources_created: int = 0
    resources_updated: int = 0
    chunks: int = 0
    bookmarks: int = 0
    views: int = 0
    reviews: int = 0
    analytics_events: int = 0
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: SeedReport) -> None:
        for name in self.__dataclass_fields__:
            if name == "warnings":
                continue
            setattr(self, name, getattr(self, name) + getattr(other, name))
        self.warnings.extend(w for w in other.warnings if w not in self.warnings)

    def counts(self) -> dict[str, int]:
        return {
            name: value
            for name, value in self.__dict__.items()
            if name != "warnings" and value
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── taxonomy ────────────────────────────────────────────


async def seed_taxonomy(state: AppState) -> SeedReport:
    """Install the academic structure: departments → subjects → topics.

    Registration validates a department against this, the ingestion classifier
    votes against the subject/topic names, and the knowledge graph mirrors it.
    """
    report = SeedReport()
    departments = build_departments()
    subjects = build_subjects()
    topics = build_topics()

    if await state.taxonomy.is_empty():
        await state.taxonomy.seed(departments, subjects, topics)
    else:
        # Not empty means either a previous seed or operator edits — and possibly
        # a partial run. Upsert per code: unique indexes hold and no duplicates.
        for department in departments:
            await state.taxonomy.upsert_department(department)
        for subject in subjects:
            await state.taxonomy.upsert_subject(subject)
        for topic in topics:
            await state.taxonomy.upsert_topic(topic)

    report.departments = len(departments)
    report.subjects = len(subjects)
    report.topics = len(topics)
    logger.info(
        "taxonomy seeded",
        event="seed_taxonomy",
        departments=report.departments,
        subjects=report.subjects,
        topics=report.topics,
    )

    if not state.graph.available:
        report.warnings.append(
            "Neo4j unavailable — taxonomy exists in MongoDB only; re-run to mirror it into the graph."
        )
        return report

    try:
        for department in departments:
            await state.graph.sync_department(department.code, department.name)
        for subject in subjects:
            await state.graph.sync_subject(
                subject.code, subject.name, subject.department_code
            )
        for topic in topics:
            await state.graph.sync_topic(topic.code, topic.name, topic.subject_code)
        report.graph_taxonomy_nodes = report.departments + report.subjects + report.topics
    except Exception as exc:  # noqa: BLE001 - the graph is a mirror, not the source of truth
        report.warnings.append(f"graph taxonomy sync incomplete: {exc}")

    return report


# ── demo users & resources ──────────────────────────────


async def seed_demo(state: AppState) -> SeedReport:
    """Install the illustrative corpus. Requires the taxonomy to classify against."""
    report = SeedReport()
    if await state.taxonomy.is_empty():
        report.merge(await seed_taxonomy(state))

    users = await _seed_users(state, report)
    resources, chunk_counts = await _seed_resources(state, report)
    await _seed_engagement(state, users, resources, chunk_counts, report)
    await _seed_analytics(state, users, resources, report)
    await _invalidate_caches(state)

    logger.info("demo data seeded", event="seed_demo", **report.counts())
    return report


async def _seed_users(state: AppState, report: SeedReport) -> dict[str, str]:
    """Returns normalized email → user_id."""
    password_hash = hash_password(DEMO_PASSWORD)  # bcrypt is slow; hash once
    user_ids: dict[str, str] = {}

    for email, student_id, name, role, department, year, semester in DEMO_USERS:
        normalized = User.normalize_email(email)
        existing = await state.users.get_by_email(normalized)
        if existing is not None:
            user_ids[normalized] = existing.user_id
            report.users_existing += 1
            user = existing
        else:
            user = User(
                user_id=await state.users.new_user_id(),
                email=normalized,
                student_id=student_id,
                name=name,
                password_hash=password_hash,
                role=Role(role),
                department_code=department,
                academic_year=year,
                semester=semester,
                profile={"is_seed_data": True, "seed_label": SEED_LABEL},
            )
            await state.users.create(user)
            user_ids[normalized] = user.user_id
            report.users_created += 1

        if state.graph.available:
            try:
                await state.graph.sync_user(
                    user_id=user.user_id,
                    department_code=user.department_code,
                    role=user.role.value,
                )
            except Exception as exc:  # noqa: BLE001
                report.warnings.append(f"graph user sync skipped for {user.user_id}: {exc}")

    return user_ids


async def _seed_resources(
    state: AppState, report: SeedReport
) -> tuple[dict[str, str], dict[str, int]]:
    """Returns (slug → resource_id, resource_id → chunk count)."""
    resource_ids: dict[str, str] = {}
    chunk_counts: dict[str, int] = {}
    graph_on = state.graph.available

    if graph_on:
        try:
            await state.graph.ensure_source(DEMO_SOURCE_NAME)
        except Exception as exc:  # noqa: BLE001
            graph_on = False
            report.warnings.append(f"graph source node skipped: {exc}")

    for entry in DEMO_RESOURCES:
        slug = entry["slug"]
        source_id = f"{DEMO_SOURCE_ID_PREFIX}:{slug}"
        # A DiscoveredItem purely to reuse the pipeline's fingerprint function,
        # so demo resources deduplicate exactly like ingested ones.
        item = DiscoveredItem(
            title=entry["title"],
            type=entry["type"],
            authors=list(entry["authors"]),
            year=entry["year"],
            description=entry["description"],
            keywords=list(entry["keywords"]),
            identifiers=ResourceIdentifiers(source_id=source_id),
            source_name=DEMO_SOURCE_NAME,
            license=DEMO_SOURCE_LICENSE,
            publisher=entry["publisher"],
            text=entry["text"],
            text_source="seed",
        )

        existing = await state.resources.find_by_identifier(kind="source_id", value=source_id)
        resource = Resource(
            resource_id=existing.resource_id if existing else await state.resources.new_resource_id(),
            type=entry["type"],
            title=entry["title"],
            subtitle=entry["subtitle"],
            description=entry["description"],
            authors=list(entry["authors"]),
            year=entry["year"],
            publisher=entry["publisher"],
            access=entry["access"],
            premium_price_usd=entry.get("price"),
            identifiers=ResourceIdentifiers(source_id=source_id),
            fingerprint=fingerprint(item),
            taxonomy=ResourceTaxonomy(
                department_code=entry["department"],
                subject_codes=list(entry["subjects"]),
                topic_codes=list(entry["topics"]),
            ),
            classification=ResourceClassification(
                method="admin",
                confidence=1.0,
                academic_level=entry["level"],
                difficulty=entry["difficulty"],
                semester=entry["semester"],
                notes=SEED_LABEL,
            ),
            keywords=list(entry["keywords"]),
            source=ResourceSource(
                name=DEMO_SOURCE_NAME, license=DEMO_SOURCE_LICENSE, id=source_id
            ),
            flags=ResourceFlags(is_seed_data=True, seed_label=SEED_LABEL),
            created_at=existing.created_at if existing else _now(),
        )

        if existing is None:
            await state.resources.insert(resource)
            report.resources_created += 1
        else:
            # stats/content are left alone: they are recomputed from engagement
            # below and by ingest_document, and must not reset on a re-run.
            await state.resources.update_fields(
                resource.resource_id,
                resource.model_dump(exclude={"resource_id", "created_at", "stats", "content"}),
            )
            report.resources_updated += 1

        resource_ids[slug] = resource.resource_id
        chunk_counts[resource.resource_id] = await _ingest_text(
            state, resource.resource_id, entry["text"], report
        )

        if graph_on:
            try:
                await state.graph.upsert_resource(
                    resource_id=resource.resource_id,
                    title=resource.title,
                    type=resource.type.value,
                    access=resource.access.value,
                    year=resource.year,
                    department_code=resource.taxonomy.department_code,
                    subject_codes=resource.taxonomy.subject_codes,
                    topic_codes=resource.taxonomy.topic_codes,
                    source_name=DEMO_SOURCE_NAME,
                )
                await state.graph.link_authors(resource.resource_id, resource.authors)
                report.graph_resources += 1
            except Exception as exc:  # noqa: BLE001
                report.warnings.append(f"graph sync skipped for {resource.title}: {exc}")

    return resource_ids, chunk_counts


async def _ingest_text(state: AppState, resource_id: str, text: str, report: SeedReport) -> int:
    try:
        chunks = await state.ai_service.ingest_document(resource_id, text, "seed")
        report.chunks += chunks
        return chunks
    except Exception as exc:  # noqa: BLE001 - RAG indexing is best-effort at seed time
        report.warnings.append(f"{resource_id}: text not indexed for AI features ({exc})")
        return 0


# ── engagement ──────────────────────────────────────────


async def _seed_engagement(
    state: AppState,
    users: dict[str, str],
    resources: dict[str, str],
    chunk_counts: dict[str, int],
    report: SeedReport,
) -> None:
    db = state.resources.db
    touched: set[str] = set()

    for email, slug, bookmarked, viewed, percent in DEMO_ENGAGEMENT:
        user_id = users.get(User.normalize_email(email))
        resource_id = resources.get(slug)
        if user_id is None or resource_id is None:
            continue

        if bookmarked and await state.bookmarks.add(user_id, resource_id):
            report.bookmarks += 1

        if viewed:
            # record_view() increments view_count on every call, so it runs only
            # the first time — a re-seed must not inflate the numbers.
            already = await db.reading_history.find_one(
                {"user_id": user_id, "resource_id": resource_id}, {"_id": 1}
            )
            if already is None:
                await state.history.record_view(user_id, resource_id)
                report.views += 1
            if percent:
                total = chunk_counts.get(resource_id, 0)
                await state.history.update_progress(
                    user_id,
                    resource_id,
                    percent=percent,
                    last_chunk=max(0, round(total * percent / 100) - 1),
                )

        if state.graph.available:
            try:
                if viewed:
                    await state.graph.record_activity(
                        user_id=user_id, resource_id=resource_id, relation="VIEWED"
                    )
                if bookmarked:
                    await state.graph.record_activity(
                        user_id=user_id, resource_id=resource_id, relation="BOOKMARKED"
                    )
            except Exception as exc:  # noqa: BLE001
                report.warnings.append(f"graph activity skipped for {slug}: {exc}")

        touched.add(resource_id)

    for email, slug, rating, title, body in DEMO_REVIEWS:
        user_id = users.get(User.normalize_email(email))
        resource_id = resources.get(slug)
        if user_id is None or resource_id is None:
            continue
        await state.reviews.upsert(
            user_id, resource_id, rating=rating, title=title, body=body
        )
        report.reviews += 1
        touched.add(resource_id)

    # Recomputed from the collections so repeated seeds converge on the same
    # numbers instead of drifting upward.
    for resource_id in sorted(touched):
        await state.reviews.refresh_resource_rating(resource_id)
        await state.resources.update_fields(
            resource_id,
            {
                "stats.bookmarks": await state.bookmarks.count_for_resource(resource_id),
                "stats.views": await db.reading_history.count_documents(
                    {"resource_id": resource_id}
                ),
            },
        )


# ── analytics ───────────────────────────────────────────


def _demo_events(
    users: dict[str, str], resources: dict[str, str]
) -> list[dict[str, Any]]:
    """Deterministic event log derived from the engagement tuples.

    Timestamps are index-derived rather than random so two seeds produce the
    same dashboard — a seed should be reproducible.
    """
    by_slug = {entry["slug"]: entry for entry in DEMO_RESOURCES}
    now = _now()
    events: list[dict[str, Any]] = []

    def add(event_type: str, offset: int, slug: str, email: str) -> None:
        entry = by_slug[slug]
        when = now - timedelta(
            days=offset % ANALYTICS_WINDOW_DAYS, hours=(offset * 5) % 24
        )
        events.append(
            {
                "event_time": when,
                "event_type": validate_event_type(event_type),
                "resource_id": validate_id(resources.get(slug)),
                "user_id": validate_id(users.get(User.normalize_email(email))),
                "department_code": validate_code(entry["department"]),
                "subject_code": validate_code(entry["subjects"][0]),
                "search_query": None,
                "result_count": None,
            }
        )

    for index, (email, slug, bookmarked, viewed, percent) in enumerate(DEMO_ENGAGEMENT):
        if viewed:
            add("view", index, slug, email)
        if percent >= 100:
            add("read", index + 1, slug, email)
        if bookmarked:
            add("bookmark", index + 2, slug, email)

    for index, (email, slug, _rating, _title, _body) in enumerate(DEMO_REVIEWS):
        add("rate", index, slug, email)
        add("review", index + 3, slug, email)

    return events


async def _seed_analytics(
    state: AppState, users: dict[str, str], resources: dict[str, str], report: SeedReport
) -> None:
    if not state.analytics.available:
        report.warnings.append(
            "MonetDB unavailable — analytics charts stay empty; re-run the seed once it is up."
        )
        return

    events = [
        event
        for event in _demo_events(users, resources)
        if event["resource_id"] and event["user_id"]
    ]
    if not events:
        return

    columns = (
        "event_time", "event_type", "resource_id", "user_id",
        "department_code", "subject_code", "search_query", "result_count",
    )
    values = ",\n".join(
        "(" + ", ".join(sql_lit(event[column]) for column in columns) + ")"
        for event in events
    )
    try:
        # Replace rather than append: MonetDB rows carry no seed flag, so the
        # only way a re-seed stays idempotent is to drop the previous batch
        # first (they are identifiable by the demo resource IDs).
        await _delete_demo_events(state, list(resources.values()), [])
        await state.analytics.adapter.execute(
            f"INSERT INTO events ({', '.join(columns)}) VALUES\n{values}"
        )
        report.analytics_events = len(events)
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(f"analytics events skipped: {exc}")


def _demo_event_filter(resource_ids: list[str], user_ids: list[str]) -> str | None:
    clauses = []
    if resource_ids:
        listed = ", ".join(sql_lit(validate_id(r)) for r in resource_ids)
        clauses.append(f"resource_id IN ({listed})")
    if user_ids:
        listed = ", ".join(sql_lit(validate_id(u)) for u in user_ids)
        clauses.append(f"user_id IN ({listed})")
    return " OR ".join(clauses) or None


async def _delete_demo_events(
    state: AppState, resource_ids: list[str], user_ids: list[str]
) -> int:
    where = _demo_event_filter(resource_ids, user_ids)
    if where is None:
        return 0
    # Counted before deleting: the driver reports no affected-row count for DML,
    # and a purge report that claims "0 removed" would be a lie.
    rows = await state.analytics.adapter.execute(f"SELECT COUNT(*) FROM events WHERE {where}")
    await state.analytics.adapter.execute(f"DELETE FROM events WHERE {where}")
    return int(rows[0][0]) if rows else 0


# ── cache ───────────────────────────────────────────────


async def _invalidate_caches(state: AppState) -> None:
    for prefix in ("home:", "search:v1:"):
        await state.cache.delete_prefix(prefix)


# ── orchestration ───────────────────────────────────────


async def seed_all(state: AppState) -> SeedReport:
    report = await seed_taxonomy(state)
    report.merge(await seed_demo(state))
    return report


# ── removal ─────────────────────────────────────────────


async def purge_demo(state: AppState) -> dict[str, int]:
    """Delete every demo document from all four stores. Taxonomy is kept:
    it is reference data, and registration depends on it."""
    db = state.resources.db
    removed: dict[str, int] = {}

    resource_ids = [
        doc["resource_id"]
        async for doc in db.resources.find(
            {"flags.is_seed_data": True}, {"_id": 0, "resource_id": 1}
        )
    ]
    user_ids = [
        doc["user_id"]
        async for doc in db.users.find(_demo_user_query(), {"_id": 0, "user_id": 1})
    ]

    for collection in _RESOURCE_DEPENDENTS:
        if not resource_ids:
            removed[collection] = 0
            continue
        result = await db[collection].delete_many({"resource_id": {"$in": resource_ids}})
        removed[collection] = result.deleted_count

    if resource_ids:
        result = await db.resources.delete_many({"resource_id": {"$in": resource_ids}})
        removed["resources"] = result.deleted_count

    for user_id in user_ids:
        # Clears the Redis session keys as well as marking the Mongo mirror.
        await state.sessions.revoke_all_for_user(user_id)
    if user_ids:
        result = await db.sessions.delete_many({"user_id": {"$in": user_ids}})
        removed["sessions"] = result.deleted_count
        result = await db.users.delete_many({"user_id": {"$in": user_ids}})
        removed["users"] = result.deleted_count

    if resource_ids and state.graph.available:
        for resource_id in resource_ids:
            try:
                await state.graph.delete_resource(resource_id)
                removed["graph_resources"] = removed.get("graph_resources", 0) + 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "graph purge incomplete", event="purge_graph_failed",
                    resource_id=resource_id, reason=str(exc)[:200],
                )

    removed["analytics_events"] = await _purge_analytics(state, resource_ids, user_ids)

    await _invalidate_caches(state)
    logger.info("demo data purged", event="purge_demo", **removed)
    return removed


def _demo_user_query() -> dict[str, Any]:
    return {
        "$or": [
            {"email": {"$in": [User.normalize_email(u[0]) for u in DEMO_USERS]}},
            {"student_id": {"$regex": f"^{_DEMO_STUDENT_ID_PREFIX}"}},
            {"profile.is_seed_data": True},
        ]
    }


async def _purge_analytics(
    state: AppState, resource_ids: list[str], user_ids: list[str]
) -> int:
    if not state.analytics.available:
        return 0
    try:
        return await _delete_demo_events(state, resource_ids, user_ids)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "analytics purge failed", event="purge_analytics_failed", reason=str(exc)[:200]
        )
        return 0
