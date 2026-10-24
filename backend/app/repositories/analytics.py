from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.core.errors import DatabaseUnavailableError
from app.databases.monetdb import MonetDBAdapter, sql_lit, validate_code, validate_event_type, validate_id

log = logging.getLogger(__name__)


class AnalyticsRepository:
    """MonetDB analytical store: append-only event log + aggregate queries.

    All dynamic values are shape-validated and rendered through sql_lit();
    column names are hard-coded constants. Rows are buffered in memory and
    flushed in batches — if MonetDB is down, events queue up to a cap and the
    flusher retries on a timer (never silently dropped below the cap)."""

    def __init__(self, adapter: MonetDBAdapter, *, flush_threshold: int = 25, flush_interval_s: float = 20.0):
        self.adapter = adapter
        self.flush_threshold = flush_threshold
        self.flush_interval_s = flush_interval_s
        self._buffer: list[dict] = []
        self._last_flush = datetime.now(timezone.utc)

    @property
    def available(self) -> bool:
        return self.adapter.available

    @property
    def pending(self) -> int:
        """Events buffered in memory, waiting on MonetDB."""
        return len(self._buffer)

    def _require_available(self) -> None:
        if not self.available:
            raise DatabaseUnavailableError("MonetDB")

    async def record(
        self,
        *,
        event_type: str,
        resource_id: str | None = None,
        user_id: str | None = None,
        department_code: str | None = None,
        subject_code: str | None = None,
        search_query: str | None = None,
        result_count: int | None = None,
    ) -> None:
        event = {
            "event_time": datetime.now(timezone.utc),
            "event_type": validate_event_type(event_type),
            "resource_id": validate_id(resource_id),
            "user_id": validate_id(user_id),
            "department_code": validate_code(department_code),
            "subject_code": validate_code(subject_code),
            "search_query": (search_query or "")[:512] or None,
            "result_count": int(result_count) if result_count is not None else None,
        }
        self._buffer.append(event)
        await self._maybe_flush()

    async def _maybe_flush(self) -> None:
        if not self.available:
            if len(self._buffer) > 5000:
                self._buffer = self._buffer[-5000:]
            return
        due = (
            len(self._buffer) >= self.flush_threshold
            or (
                self._buffer
                and (datetime.now(timezone.utc) - self._last_flush).total_seconds()
                >= self.flush_interval_s
            )
        )
        if due:
            await self.flush()

    async def flush(self) -> int:
        if not self._buffer or not self.available:
            return 0
        batch, self._buffer = self._buffer[:500], self._buffer[500:]
        if not batch:
            return 0
        values = ",\n".join(
            "(" + ", ".join(
                sql_lit(e[k]) for k in (
                    "event_time", "event_type", "resource_id", "user_id",
                    "department_code", "subject_code", "search_query", "result_count",
                )
            ) + ")"
            for e in batch
        )
        sql = (
            f"INSERT INTO events (event_time, event_type, resource_id, user_id, "
            f"department_code, subject_code, search_query, result_count) VALUES\n{values}"
        )
        try:
            await self.adapter.execute(sql)
        except Exception as exc:
            log.error(
                "Analytics flush failed, re-queuing %d events: %s", len(batch), exc,
                extra={"event": "analytics_flush_failed"},
            )
            self._buffer = batch + self._buffer[:5000 - len(batch)]
            return 0
        self._last_flush = datetime.now(timezone.utc)
        return len(batch)

    # ── aggregates ──────────────────────────────────────

    async def summary(self) -> dict:
        self._require_available()
        since = datetime.now(timezone.utc) - timedelta(days=7)
        total_events = (await self.adapter.execute("SELECT COUNT(*) FROM events"))[0][0]
        last7 = (
            await self.adapter.execute(
                f"SELECT COUNT(*) FROM events WHERE event_time >= {sql_lit(since)}"
            )
        )[0][0]
        return {"total_events": total_events, "last_7_days": last7}

    async def top_resources(self, *, event_type: str = "view", limit: int = 10) -> list[dict]:
        self._require_available()
        et = sql_lit(validate_event_type(event_type))
        lim = sql_lit(int(limit))
        rows = await self.adapter.execute(
            f"""
            SELECT resource_id, COUNT(*) AS cnt
            FROM events
            WHERE event_type = {et} AND resource_id IS NOT NULL
            GROUP BY resource_id
            ORDER BY cnt DESC
            LIMIT {lim}
            """
        )
        return [{"resource_id": r[0], "count": r[1]} for r in rows]

    async def event_counts_by_resource(self, resource_ids: list[str], *, since_days: int = 30) -> dict[str, dict[str, int]]:
        """Aggregated view/read/download counts for a set of resources."""
        if not resource_ids or not self.available:
            return {}
        cleaned = [validate_id(r) for r in resource_ids]
        id_list = ", ".join(sql_lit(r) for r in cleaned)
        since = sql_lit(datetime.now(timezone.utc) - timedelta(days=since_days))
        rows = await self.adapter.execute(
            f"""
            SELECT resource_id, event_type, COUNT(*)
            FROM events
            WHERE resource_id IN ({id_list}) AND event_time >= {since}
            GROUP BY resource_id, event_type
            """
        )
        out: dict[str, dict[str, int]] = {}
        for rid, etype, cnt in rows:
            out.setdefault(rid, {})[etype] = cnt
        return out

    async def popular_subjects(self, *, limit: int = 10) -> list[dict]:
        self._require_available()
        lim = sql_lit(int(limit))
        rows = await self.adapter.execute(
            f"""
            SELECT subject_code, department_code, COUNT(*) AS cnt
            FROM events
            WHERE subject_code IS NOT NULL
            GROUP BY subject_code, department_code
            ORDER BY cnt DESC
            LIMIT {lim}
            """
        )
        return [
            {"subject_code": r[0], "department_code": r[1], "events": r[2]}
            for r in rows
        ]

    async def popular_departments(self, *, limit: int = 13) -> list[dict]:
        self._require_available()
        lim = sql_lit(int(limit))
        rows = await self.adapter.execute(
            f"""
            SELECT department_code, COUNT(*) AS cnt
            FROM events
            WHERE department_code IS NOT NULL
            GROUP BY department_code
            ORDER BY cnt DESC
            LIMIT {lim}
            """
        )
        return [{"department_code": r[0], "events": r[1]} for r in rows]

    async def daily_activity(self, *, days: int = 14) -> list[dict]:
        self._require_available()
        since = sql_lit(datetime.now(timezone.utc) - timedelta(days=days))
        rows = await self.adapter.execute(
            f"""
            SELECT CAST(event_time AS DATE) AS day, event_type, COUNT(*)
            FROM events
            WHERE event_time >= {since}
            GROUP BY day, event_type
            ORDER BY day
            """
        )
        by_day: dict[str, dict] = {}
        for day, etype, cnt in rows:
            key = str(day)
            entry = by_day.setdefault(key, {"day": key, "searches": 0, "views": 0, "reads": 0})
            if etype in ("view", "read", "search"):
                entry[f"{etype}es" if etype == "search" else f"{etype}s"] = cnt
        return list(by_day.values())

    async def top_searches(self, *, limit: int = 10) -> list[dict]:
        self._require_available()
        lim = sql_lit(int(limit))
        rows = await self.adapter.execute(
            f"""
            SELECT search_query, COUNT(*) AS cnt, AVG(NULLIF(result_count, 0)) AS avg_results
            FROM events
            WHERE event_type = 'search' AND search_query IS NOT NULL AND search_query <> ''
            GROUP BY search_query
            ORDER BY cnt DESC
            LIMIT {lim}
            """
        )
        return [
            {"query": r[0], "count": r[1], "avg_results": round(float(r[2] or 0), 1)}
            for r in rows
        ]

    async def trending_resources(self, *, days: int = 14, limit: int = 10) -> list[dict]:
        """Trending = recent weighted activity (views + 2×reads + 3×bookmarks)."""
        self._require_available()
        since = sql_lit(datetime.now(timezone.utc) - timedelta(days=days))
        lim = sql_lit(int(limit))
        rows = await self.adapter.execute(
            f"""
            SELECT resource_id,
                   SUM(CASE event_type WHEN 'view' THEN 1
                                       WHEN 'read' THEN 2
                                       WHEN 'bookmark' THEN 3
                                       WHEN 'download' THEN 2 ELSE 0 END) AS score
            FROM events
            WHERE event_time >= {since} AND resource_id IS NOT NULL
            GROUP BY resource_id
            ORDER BY score DESC
            LIMIT {lim}
            """
        )
        return [{"resource_id": r[0], "score": int(r[1] or 0)} for r in rows]
