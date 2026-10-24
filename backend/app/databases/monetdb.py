from __future__ import annotations

import asyncio
import datetime as dt
import logging
import queue
import re
import threading
import time

import pymonetdb

from app.core.config import Settings
from app.databases.base import DatabaseAdapter

log = logging.getLogger(__name__)

_POOL_SIZE = 4
_CONNECT_TIMEOUT_S = 8

# Values that reach SQL as literals are constrained to these shapes; anything
# else is rejected instead of interpolated.
_ID_RE = re.compile(r"^[A-Za-z0-9_\-:.]{1,64}$")
_EVENT_TYPES = {
    "view", "read", "search", "bookmark", "download", "rate", "review",
    "ingest", "ai_overview", "ai_chat", "ai_reading", "register",
}
# Taxonomy codes are uppercase by convention (CS, CS-OS), so the shape check
# allows both cases while still rejecting quotes, spaces and statement
# separators before anything reaches SQL.
_CODES_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")

EVENTS_TABLE = "events"


def sql_lit(value) -> str:
    """Render a Python value as a single safe MonetDB SQL literal.

    Every dynamic value crossing into SQL passes through here after being
    shape-validated by callers; free text is quote-escaped and length-capped.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(int(value))
    if isinstance(value, float):
        return repr(float(value))
    if isinstance(value, dt.datetime):
        return f"TIMESTAMP '{value.strftime('%Y-%m-%d %H:%M:%S')}'"
    if isinstance(value, dt.date):
        return f"DATE '{value.isoformat()}'"
    if isinstance(value, str):
        cleaned = "".join(ch for ch in value if ch >= " " or ch in "\t")
        cleaned = cleaned.replace("'", "''")
        return f"'{cleaned[:1024]}'"
    raise TypeError(f"Unsupported SQL literal type: {type(value)!r}")


def validate_event_type(value: str) -> str:
    if value not in _EVENT_TYPES:
        raise ValueError(f"Unknown analytics event type: {value!r}")
    return value


def validate_id(value: str | None) -> str | None:
    if value is None:
        return None
    if not _ID_RE.match(value):
        raise ValueError(f"Unsafe identifier for analytics: {value!r}")
    return value


def validate_code(value: str | None) -> str | None:
    if value is None:
        return None
    if not _CODES_RE.match(value):
        raise ValueError(f"Unsafe code for analytics: {value!r}")
    return value


class MonetDBAdapter(DatabaseAdapter):
    """MonetDB — columnar analytical store.

    pymonetdb is synchronous, so all access is bridged to asyncio through a
    thread executor and a small connection pool guarded by a lock per
    connection.
    """

    name = "MonetDB"

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self._pool: queue.Queue[pymonetdb.Connection] = queue.Queue()
        self._lock = threading.Lock()
        self._closed = True

    def _new_connection(self) -> pymonetdb.Connection:
        return pymonetdb.connect(
            hostname=self.settings.monetdb_host,
            port=self.settings.monetdb_port,
            username=self.settings.monetdb_user,
            password=self.settings.monetdb_password,
            database=self.settings.monetdb_database,
            autocommit=True,
        )

    async def connect(self) -> None:
        started = time.monotonic()
        conn = await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(None, self._new_connection),
            timeout=_CONNECT_TIMEOUT_S,
        )
        self._pool.put(conn)
        self._closed = False
        await self._ensure_schema()
        for _ in range(_POOL_SIZE - 1):
            try:
                self._pool.put(await asyncio.get_running_loop().run_in_executor(None, self._new_connection))
            except Exception:
                log.warning("MonetDB pool prefill incomplete", extra={"event": "monetdb_pool"})
        self._mark_connected((time.monotonic() - started) * 1000)

    async def close(self) -> None:
        with self._lock:
            self._closed = True
        while True:
            try:
                conn = self._pool.get_nowait()
            except queue.Empty:
                break
            try:
                conn.close()
            except Exception:
                pass

    async def ping(self) -> None:
        await self.execute(f"SELECT 1")

    async def _ensure_schema(self) -> None:
        await self.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {EVENTS_TABLE} (
                event_time      TIMESTAMP,
                event_type      VARCHAR(32),
                resource_id     VARCHAR(64),
                user_id         VARCHAR(64),
                department_code VARCHAR(64),
                subject_code    VARCHAR(64),
                search_query    VARCHAR(512),
                result_count    INTEGER,
                latency_ms      INTEGER
            )
            """
        )
        log.info("MonetDB analytics schema ensured", extra={"event": "monetdb_schema"})

    async def execute(self, sql: str) -> list[tuple]:
        """Run one statement. Returns rows (empty for DML). Raises on failure."""
        return await asyncio.get_running_loop().run_in_executor(None, self._execute_sync, sql)

    def _execute_sync(self, sql: str) -> list[tuple]:
        try:
            conn = self._pool.get(timeout=5)
        except queue.Empty as exc:
            raise RuntimeError("MonetDB connection pool exhausted") from exc
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = [] if cursor.description is None else cursor.fetchall()
            cursor.close()
            healthy = True
            return rows
        except Exception:
            healthy = False
            try:
                conn.close()
            except Exception:
                pass
            raise
        finally:
            if healthy and not self._closed:
                self._pool.put(conn)

    async def execute_many(self, statements: list[str]) -> None:
        for sql in statements:
            await self.execute(sql)
