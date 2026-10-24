from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import Settings
from app.core.errors import (
    ConflictError,
    DatabaseUnavailableError,
    InvalidInputError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.logging import get_logger
from app.ingestion.classifier import RuleClassifier
from app.ingestion.dedup import fingerprint, identifier_kinds, merge_metadata
from app.ingestion.sources.arxiv import ArxivAdapter
from app.ingestion.sources.base import DiscoveredItem, SourceAdapter
from app.ingestion.sources.crossref import CrossrefAdapter
from app.ingestion.sources.doaj import DOAJAdapter
from app.ingestion.sources.openlibrary import OpenLibraryAdapter
from app.ingestion.sources.youtube import YouTubeSourceAdapter
from app.models.ingestion import IngestionRun, SourceConfig
from app.models.resource import (
    AccessType,
    Resource,
    ResourceContent,
    ResourceFlags,
    ResourceSource,
    YouTubeInfo,
)
from app.repositories.analytics import AnalyticsRepository
from app.repositories.cache import CacheRepository
from app.repositories.graph import GraphRepository
from app.repositories.resources import ResourceRepository
from app.repositories.taxonomy import TaxonomyRepository
from app.services.ai_service import AIService
from app.services.youtube_service import YouTubeService

logger = get_logger(__name__)

MAX_RETRY_ATTEMPTS = 5
RETRY_BATCH = 25

DEFAULT_SOURCES: list[dict[str, Any]] = [
    {
        "source_key": "arxiv",
        "name": "arXiv (research papers)",
        "adapter": "arxiv",
        "schedule_minutes": 720,
        "config": {
            "limit": 24,
            "fetch_full_text": True,
            "queries": [
                "deep learning intrusion detection",
                "graph neural networks",
                "large language model education",
                "operating systems process scheduling",
                "query optimization database systems",
                "computer vision medical imaging",
            ],
        },
    },
    {
        "source_key": "crossref",
        "name": "Crossref (DOI metadata)",
        "adapter": "crossref",
        "schedule_minutes": 1440,
        "config": {
            "limit": 24,
            "queries": [
                "artificial intelligence in healthcare",
                "blockchain supply chain",
                "internet of things security",
                "software engineering education",
                "renewable energy smart grid",
                "machine learning materials science",
            ],
        },
    },
    {
        "source_key": "openlibrary",
        "name": "Open Library (books)",
        "adapter": "openlibrary",
        "schedule_minutes": 10080,
        "config": {
            "limit": 30,
            "queries": [
                "operating systems",
                "data structures and algorithms",
                "database management systems",
                "computer networks",
                "software engineering",
                "machine learning",
                "engineering thermodynamics",
                "structural analysis",
                "organic chemistry",
                "linear algebra",
            ],
        },
    },
    {
        "source_key": "doaj",
        "name": "DOAJ (open access journals)",
        "adapter": "doaj",
        "schedule_minutes": 1440,
        "config": {
            "limit": 20,
            "queries": [
                "deepfake detection",
                "natural language processing education",
                "cybersecurity awareness university",
                "biotechnology fermentation",
            ],
        },
    },
    {
        "source_key": "youtube",
        "name": "YouTube (educational videos)",
        "adapter": "youtube",
        "requires_api_key": True,
        "schedule_minutes": 1440,
        "config": {
            "limit": 16,
            "queries": [
                "operating systems full course",
                "graph algorithms tutorial",
                "database management system tutorial",
                "machine learning course",
                "computer networks lecture series",
            ],
        },
    },
]


class IngestionService:
    """Automatic discovery pipeline:

    SOURCE -> DISCOVERY -> FETCH METADATA -> VALIDATION -> NORMALIZATION ->
    DUPLICATE DETECTION -> CLASSIFICATION -> RESOURCE ID -> MONGODB ->
    NEO4J -> MONETDB -> REDIS -> SEARCH INDEX (Mongo text index)

    Every stage failure is either tolerated with degradation (graph/analytics/
    cache) or queued for retry (persist). Nothing is ever fabricated."""

    def __init__(
        self,
        settings: Settings,
        db: AsyncIOMotorDatabase,
        resources: ResourceRepository,
        taxonomy: TaxonomyRepository,
        graph: GraphRepository,
        analytics: AnalyticsRepository,
        cache: CacheRepository,
        youtube: YouTubeService | None = None,
        ai_service: AIService | None = None,
    ) -> None:
        self._settings = settings
        self._db = db
        self._resources = resources
        self._taxonomy = taxonomy
        self._graph = graph
        self._analytics = analytics
        self._cache = cache
        self._youtube = youtube
        self._ai = ai_service
        self._classifier = RuleClassifier(taxonomy)
        self._adapters: dict[str, SourceAdapter] = {}
        self._adapters["arxiv"] = ArxivAdapter(settings)
        self._adapters["crossref"] = CrossrefAdapter(settings)
        self._adapters["openlibrary"] = OpenLibraryAdapter(settings)
        self._adapters["doaj"] = DOAJAdapter(settings)
        if youtube is not None:
            self._adapters["youtube"] = YouTubeSourceAdapter(settings, youtube)

    # ------------------------------------------------------------ sources

    async def ensure_sources(self) -> None:
        """Insert default source configs; never overwrite admin edits."""
        for default in DEFAULT_SOURCES:
            await self._db.sources.update_one(
                {"source_key": default["source_key"]},
                {"$setOnInsert": SourceConfig(**default).model_dump()},
                upsert=True,
            )

    def adapter_availability(self, adapter: str) -> tuple[bool, str | None]:
        """(registered_and_configured, honest_reason) for one adapter name."""
        registered = self._adapters.get(adapter)
        if registered is None:
            return False, f"No adapter registered for '{adapter}'"
        return True, registered.unavailable_reason()

    async def list_sources(self) -> list[dict[str, Any]]:
        cursor = self._db.sources.find({}, {"_id": 0}).sort("source_key", 1)
        sources = [doc async for doc in cursor]
        for source in sources:
            available, reason = self.adapter_availability(source.get("adapter", ""))
            source["adapter_available"] = available
            source["unavailable_reason"] = reason
            source["requires_api_key"] = bool(source.get("requires_api_key"))
        return sources

    async def get_source(self, source_key: str) -> SourceConfig:
        doc = await self._db.sources.find_one({"source_key": source_key}, {"_id": 0})
        if not doc:
            raise NotFoundError(f"Source '{source_key}' is not configured")
        return SourceConfig.model_validate(doc)

    async def update_source(
        self, source_key: str, *, enabled: bool | None = None,
        schedule_minutes: int | None = None,
    ) -> SourceConfig:
        updates: dict[str, Any] = {}
        if enabled is not None:
            updates["enabled"] = enabled
        if schedule_minutes is not None:
            updates["schedule_minutes"] = int(schedule_minutes)
        if not updates:
            raise InvalidInputError("Provide 'enabled' and/or 'schedule_minutes'")
        doc = await self._db.sources.find_one_and_update(
            {"source_key": source_key}, {"$set": updates}, return_document=True,
        )
        if not doc:
            raise NotFoundError(f"Source '{source_key}' is not configured")
        doc.pop("_id", None)
        return SourceConfig.model_validate(doc)

    async def update_source_config(self, source_key: str, config: dict[str, Any]) -> SourceConfig:
        allowed: dict[str, Any] = {}
        if config.get("queries") is not None:
            queries = [re.sub(r"\s+", " ", str(q)).strip()[:120] for q in config["queries"]]
            allowed["queries"] = list(dict.fromkeys(q for q in queries if q))
        if config.get("limit") is not None:
            allowed["limit"] = int(config["limit"])
        if config.get("fetch_full_text") is not None:
            allowed["fetch_full_text"] = bool(config["fetch_full_text"])
        if not allowed:
            raise InvalidInputError(
                "No updatable fields provided (queries, limit, fetch_full_text)"
            )
        doc = await self._db.sources.find_one_and_update(
            {"source_key": source_key},
            {"$set": {f"config.{k}": v for k, v in allowed.items()}},
            return_document=True,
        )
        if not doc:
            raise NotFoundError(f"Source '{source_key}' is not configured")
        doc.pop("_id", None)
        return SourceConfig.model_validate(doc)

    # ------------------------------------------------------------ runs

    async def sync_all(
        self, *, triggered_by: str = "scheduler", due_only: bool = False
    ) -> dict[str, Any]:
        """Run every eligible source.

        With due_only=True a source runs only when its own `schedule_minutes`
        has elapsed since `last_run_at` — that is the mode the background
        worker ticks on, so each source keeps the cadence its adapter set.
        """
        if not self._settings.sync_enabled:
            return {"ran": [], "skipped": [], "disabled": "sync disabled by configuration"}
        sources = await self.list_sources()
        now = _utcnow()
        ran: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        for source in sources:
            key = source["source_key"]
            adapter = self._adapters.get(source.get("adapter", ""))
            if not source.get("enabled"):
                skipped.append({"source_key": key, "reason": "disabled by configuration"})
            elif adapter is None:
                skipped.append({"source_key": key, "reason": "no adapter registered"})
            elif (reason := adapter.unavailable_reason()):
                skipped.append({"source_key": key, "reason": reason})
            elif due_only and not _is_due(source, now):
                continue
            else:
                try:
                    run = await self.run_source(key, triggered_by=triggered_by)
                except Exception as exc:  # noqa: BLE001 - one source must not stop the rest
                    logger.error("source_run_failed", source=key, reason=str(exc)[:200])
                    skipped.append({"source_key": key, "reason": str(exc)[:200]})
                    continue
                ran.append(run.model_dump(mode="json"))
        return {"ran": ran, "skipped": skipped}

    async def run_source(self, source_key: str, *, triggered_by: str = "admin",
                         limit: int | None = None) -> IngestionRun:
        source = await self.get_source(source_key)
        adapter = self._adapters.get(source.adapter)
        if adapter is None:
            raise ServiceUnavailableError(f"No adapter registered for '{source.adapter}'")
        reason = adapter.unavailable_reason()
        if reason:
            raise ServiceUnavailableError(reason)
        config = source.config or {}
        queries = list(config.get("queries") or [])
        if not queries:
            raise InvalidInputError(f"Source '{source_key}' has no discovery queries configured")
        effective_limit = min(int(limit or config.get("limit", 20)), 60)

        run = IngestionRun(
            run_id=await self._next_run_id(),
            source_key=source_key,
            triggered_by=triggered_by,
        )
        await self._save_run(run)
        await self._classifier.load()
        try:
            items = await adapter.discover(queries, effective_limit)
        except Exception as exc:  # noqa: BLE001 - a source outage is a run failure
            logger.warning("source_discovery_failed", source=source_key, reason=str(exc)[:300])
            run.status = "failed"
            run.finished_at = _utcnow()
            run.error_samples = [f"discovery: {exc.__class__.__name__}: {str(exc)[:200]}"]
            await self._save_run(run)
            await self._update_source_last_run(source_key, run)
            return run

        run.discovered = len(items)
        for item in items:
            status = await self._process_item(item, run, source_key)
            if status == "added":
                run.added += 1
            elif status == "updated":
                run.updated += 1
            elif status == "merged":
                run.merged += 1
            elif status == "duplicate":
                run.duplicates_skipped += 1
            elif status == "failed":
                run.failures += 1

        run.status = "ok" if run.failures == 0 else ("partial" if run.added or run.merged else "failed")
        run.finished_at = _utcnow()
        await self._save_run(run)
        await self._update_source_last_run(source_key, run)
        await self._cache.delete_prefix("home:")
        await self._cache.delete_prefix("search:v1:")
        logger.info("ingestion_run_complete", source=source_key, added=run.added,
                    merged=run.merged, duplicates=run.duplicates_skipped,
                    failures=run.failures)
        return run

    async def recent_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        cursor = self._db.ingestion_runs.find({}, {"_id": 0}).sort("started_at", -1).limit(limit)
        return [doc async for doc in cursor]

    async def _save_run(self, run: IngestionRun) -> None:
        await self._db.ingestion_runs.update_one(
            {"run_id": run.run_id}, {"$set": run.model_dump(mode="json")}, upsert=True,
        )

    async def _update_source_last_run(self, source_key: str, run: IngestionRun) -> None:
        await self._db.sources.update_one(
            {"source_key": source_key},
            {"$set": {"last_run_at": run.finished_at or _utcnow(),
                      "last_run_status": run.status}},
        )

    async def _next_run_id(self) -> str:
        from app.repositories.counters import next_id
        return await next_id(self._db, "run")

    # ------------------------------------------------------------ pipeline

    async def _process_item(self, item: DiscoveredItem, run: IngestionRun | None,
                            source_key: str) -> str:
        try:
            self._validate(item)
            item = self._normalize(item)
            return await self._dedup_and_persist(item, source_key)
        except InvalidItemError as exc:
            if run is not None and len(run.error_samples) < 10:
                run.error_samples.append(f"validate: {exc}")
            return "failed"
        except Exception as exc:  # noqa: BLE001 - queue for retry, never crash the run
            logger.warning("ingestion_item_failed", source=source_key,
                           title=item.title[:80], reason=str(exc)[:200])
            if run is not None and len(run.error_samples) < 10:
                run.error_samples.append(f"{item.title[:60]}: {exc.__class__.__name__}")
            await self._queue_retry(source_key, "persist", item.model_dump(mode="json"), str(exc))
            return "failed"

    def _validate(self, item: DiscoveredItem) -> None:
        if not item.title or len(item.title.strip()) < 8:
            raise InvalidItemError("title too short")
        if not identifier_kinds(item) and not item.source_url:
            raise InvalidItemError("no identifier and no source URL")
        if item.year is not None and not (1500 <= item.year <= 2100):
            item.year = None

    def _normalize(self, item: DiscoveredItem) -> DiscoveredItem:
        item.title = re.sub(r"\s+", " ", item.title).strip()[:400]
        item.authors = [re.sub(r"\s+", " ", a).strip()[:120]
                        for a in item.authors if a and a.strip()][:12]
        item.keywords = [k.strip().lower()[:60] for k in item.keywords if k and k.strip()][:16]
        if item.description:
            item.description = re.sub(r"\s+", " ", item.description).strip()[:4000]
        if item.identifiers.source_id:
            item.identifiers.source_id = f"{item.source_name}:{item.identifiers.source_id}"
        if item.identifiers.doi:
            item.identifiers.doi = item.identifiers.doi.strip().lower()[:200]
        if item.identifiers.isbn:
            item.identifiers.isbn = re.sub(r"[^0-9Xx]", "", item.identifiers.isbn)[:17] or None
        return item

    async def _dedup_and_persist(self, item: DiscoveredItem, source_key: str) -> str:
        for kind, value in identifier_kinds(item):
            existing = await self._resources.find_by_identifier(kind=kind, value=value)
            if existing:
                return await self._merge_into(existing, item)
        fp = fingerprint(item)
        existing = await self._resources.find_by_fingerprint(fp)
        if existing:
            updates = merge_metadata(existing, item)
            if updates:
                return await self._merge_into(existing, item)
            return "duplicate"
        return await self._persist_new(item, fp)

    async def _merge_into(self, existing: Resource, item: DiscoveredItem) -> str:
        updates = merge_metadata(existing, item)
        if not updates:
            return "duplicate"
        try:
            updated = await self._resources.update_fields(existing.resource_id, updates)
        except Exception as exc:  # noqa: BLE001
            logger.warning("merge_update_failed", resource_id=existing.resource_id,
                           reason=str(exc)[:200])
            return "failed"
        if updated is None:
            return "duplicate"
        await self._safe_graph_sync(updated, item.source_name)
        return "merged"

    async def _persist_new(self, item: DiscoveredItem, fp: str) -> str:
        taxonomy, classification, keywords = self._classifier.classify(item)
        resource = Resource(
            resource_id=await self._resources.new_resource_id(),
            type=item.type,
            title=item.title,
            description=item.description,
            authors=item.authors,
            year=item.year,
            publisher=item.publisher,
            language=item.language or "en",
            access=AccessType.FREE,
            identifiers=item.identifiers,
            fingerprint=fp,
            taxonomy=taxonomy,
            classification=classification,
            keywords=keywords,
            source=ResourceSource(
                name=item.source_name, url=item.source_url,
                license=item.license, id=item.identifiers.source_id,
            ),
            youtube=YouTubeInfo(**item.youtube) if item.youtube else None,
            flags=ResourceFlags(is_seed_data=False),
            citation_count=item.citation_count,
            content=ResourceContent(
                text_available=bool(item.text),
                text_source=item.text_source if item.text else None,
                text_length=len(item.text or ""),
            ),
        )
        try:
            resource = await self._resources.insert(resource)
        except ConflictError:
            return "duplicate"
        await self._ensure_taxonomy_nodes(taxonomy.department_code, taxonomy.subject_codes,
                                          taxonomy.topic_codes)
        await self._safe_graph_sync(resource, item.source_name)
        try:
            await self._analytics.record(
                event_type="ingest", resource_id=resource.resource_id,
                department_code=taxonomy.department_code,
                subject_code=taxonomy.subject_codes[0] if taxonomy.subject_codes else None,
            )
        except Exception as exc:  # noqa: BLE001 - analytics degradation
            logger.info("ingest_analytics_skipped", reason=str(exc)[:160])
        await self._ingest_text(resource, item)
        return "added"

    async def _ingest_text(self, resource: Resource, item: DiscoveredItem) -> None:
        if self._ai is None:
            return
        text = item.text or ""
        text_source = item.text_source or "description"
        # arXiv PDFs are open access; fetch real full text when configured.
        if not text and item.source_name == "arxiv" and item.identifiers.url:
            adapter = self._adapters.get("arxiv")
            if isinstance(adapter, ArxivAdapter):
                pdf_url = item.identifiers.url.replace("/abs/", "/pdf/")
                text = await adapter.fetch_full_text(pdf_url)
                text_source = "pdf"
        if not text:
            return
        try:
            chunks = await self._ai.ingest_document(resource.resource_id, text, text_source)
            logger.info("resource_text_ingested", resource_id=resource.resource_id, chunks=chunks)
        except Exception as exc:  # noqa: BLE001 - RAG ingestion is best-effort
            logger.warning("resource_text_ingest_failed",
                           resource_id=resource.resource_id, reason=str(exc)[:200])

    # -------------------------------------------------------------- graph

    async def _ensure_taxonomy_nodes(self, department: str | None,
                                     subjects: list[str], topics: list[str]) -> None:
        try:
            if department:
                dept = await self._taxonomy.get_department(department)
                await self._graph.sync_department(dept.code, dept.name)
            for code in subjects:
                subject = await self._taxonomy.get_subject(code)
                await self._graph.sync_subject(subject.code, subject.name, subject.department_code)
            for code in topics:
                topic = await self._taxonomy.get_topic(code)
                await self._graph.sync_topic(topic.code, topic.name, topic.subject_code)
        except DatabaseUnavailableError:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.info("graph_taxonomy_sync_skipped", reason=str(exc)[:160])

    async def _safe_graph_sync(self, resource: Resource, source_name: str | None) -> None:
        try:
            if source_name:
                await self._graph.ensure_source(source_name)
            await self._graph.upsert_resource(
                resource_id=resource.resource_id,
                title=resource.title,
                type=resource.type.value,
                access=resource.access.value,
                year=resource.year,
                department_code=resource.taxonomy.department_code,
                subject_codes=resource.taxonomy.subject_codes,
                topic_codes=resource.taxonomy.topic_codes,
                source_name=source_name,
            )
            if resource.authors:
                await self._graph.link_authors(resource.resource_id, resource.authors)
        except DatabaseUnavailableError:
            await self._queue_retry("graph", "graph",
                                    {"resource_id": resource.resource_id},
                                    "Neo4j unavailable")
        except Exception as exc:  # noqa: BLE001
            logger.warning("graph_sync_failed", resource_id=resource.resource_id,
                           reason=str(exc)[:200])
            await self._queue_retry("graph", "graph",
                                    {"resource_id": resource.resource_id}, str(exc)[:200])

    # ---------------------------------------------------------- retry queue

    async def _queue_retry(self, source_key: str, stage: str, payload: dict, error: str) -> None:
        try:
            await self._db.ingestion_retry_queue.update_one(
                {"source_key": source_key, "stage": stage,
                 "payload_key": _payload_key(payload)},
                {"$set": {
                    "source_key": source_key, "stage": stage, "payload": payload,
                    "payload_key": _payload_key(payload),
                    "next_attempt_at": _utcnow() + timedelta(minutes=5),
                    "last_error": error[:300],
                }, "$setOnInsert": {"attempts": 0}},
                upsert=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("retry_queue_insert_failed", reason=str(exc)[:160])

    async def process_retries(self, *, limit: int = RETRY_BATCH) -> dict[str, int]:
        now = _utcnow()
        cursor = self._db.ingestion_retry_queue.find(
            {"next_attempt_at": {"$lte": now}, "attempts": {"$lt": MAX_RETRY_ATTEMPTS}},
            {"_id": 1, "source_key": 1, "stage": 1, "payload": 1, "attempts": 1},
        ).sort("next_attempt_at", 1).limit(limit)
        processed = succeeded = failed = 0
        async for doc in cursor:
            processed += 1
            try:
                if doc["stage"] == "graph":
                    await self._retry_graph(doc["payload"].get("resource_id", ""))
                else:
                    item = DiscoveredItem.model_validate(doc["payload"])
                    self._validate(item)
                    item = self._normalize(item)
                    await self._dedup_and_persist(item, doc["source_key"])
                await self._db.ingestion_retry_queue.delete_one({"_id": doc["_id"]})
                succeeded += 1
                logger.info("retry_succeeded", stage=doc["stage"], source=doc["source_key"])
            except Exception as exc:  # noqa: BLE001 - exponential backoff
                attempts = int(doc.get("attempts", 0)) + 1
                backoff = timedelta(minutes=min(2 ** attempts, 240))
                await self._db.ingestion_retry_queue.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"attempts": attempts, "next_attempt_at": now + backoff,
                              "last_error": str(exc)[:300]}},
                )
                failed += 1
        return {"processed": processed, "succeeded": succeeded, "failed": failed}

    async def _retry_graph(self, resource_id: str) -> None:
        resource = await self._resources.get(resource_id)
        await self._graph.upsert_resource(
            resource_id=resource.resource_id,
            title=resource.title,
            type=resource.type.value,
            access=resource.access.value,
            year=resource.year,
            department_code=resource.taxonomy.department_code,
            subject_codes=resource.taxonomy.subject_codes,
            topic_codes=resource.taxonomy.topic_codes,
            source_name=resource.source.name if resource.source else None,
        )
        if resource.authors:
            await self._graph.link_authors(resource.resource_id, resource.authors)

    async def retry_queue_depth(self) -> int:
        return await self._db.ingestion_retry_queue.count_documents({})

    # -------------------------------------------------------------- status

    async def status(self) -> dict[str, Any]:
        sources = await self.list_sources()
        runs = await self.recent_runs(limit=5)
        totals = {
            "resources": await self._resources.count(),
            "seed_resources": await self._resources.seed_count(),
            "retry_queue": await self.retry_queue_depth(),
        }
        return {
            "sources": sources,
            "recent_runs": runs,
            "totals": totals,
            "sync_enabled": self._settings.sync_enabled,
            "sync_interval_minutes": self._settings.sync_interval_minutes,
        }


class InvalidItemError(Exception):
    pass


def _payload_key(payload: dict) -> str:
    if "resource_id" in payload:
        return f"res:{payload['resource_id']}"
    title = (payload.get("title") or "")[:80].lower()
    return f"item:{title}"


def _is_due(source: dict, now: datetime) -> bool:
    last = source.get("last_run_at")
    if last is None:
        return True
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    interval = int(source.get("schedule_minutes") or 1440)
    return now >= last + timedelta(minutes=interval)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
