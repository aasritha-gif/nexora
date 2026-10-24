from __future__ import annotations

import abc
import asyncio
import time
from enum import Enum


class DatabaseStatus(str, Enum):
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISABLED = "disabled"


class DatabaseAdapter(abc.ABC):
    """One adapter per database. Adapters never raise out of connect() at
    startup — a failed database degrades the system instead of killing it."""

    name: str = "database"

    def __init__(self) -> None:
        self.status = DatabaseStatus.DISABLED
        self.reason = "not yet started"
        self.latency_ms: float | None = None
        self.connected_at: str | None = None

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish connections. Raises on failure (caller marks DEGRADED)."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Release connections. Must never raise."""

    @abc.abstractmethod
    async def ping(self) -> None:
        """Cheap liveness probe. Raises on failure."""

    @property
    def available(self) -> bool:
        return self.status == DatabaseStatus.CONNECTED

    def _mark_connected(self, latency_ms: float) -> None:
        from app.core.logging import utc_now_iso

        self.status = DatabaseStatus.CONNECTED
        self.reason = ""
        self.latency_ms = round(latency_ms, 1)
        self.connected_at = utc_now_iso()

    def mark_degraded(self, reason: str) -> None:
        self.status = DatabaseStatus.DEGRADED
        self.reason = self._sanitize_reason(reason)
        self.latency_ms = None

    @staticmethod
    def _sanitize_reason(reason: str) -> str:
        """Strip credentials/hosts from low-level driver errors before they
        surface in /health or logs."""
        lowered = reason.lower()
        for marker in ("password", "authorization", "auth"):
            if marker in lowered:
                return "Authentication or authorization failed"
        if "timed out" in lowered or "timeout" in lowered:
            return "Connection timed out"
        if "refused" in lowered or "unreachable" in lowered or "resolve" in lowered:
            return "Connection unavailable"
        return reason[:200]

    async def health_check(self) -> None:
        if self.status == DatabaseStatus.DISABLED:
            return
        started = time.monotonic()
        try:
            await asyncio.wait_for(self.ping(), timeout=5)
        except asyncio.TimeoutError:
            self.mark_degraded("Connection timed out")
        except Exception as exc:
            self.mark_degraded(str(exc))
        else:
            self._mark_connected((time.monotonic() - started) * 1000)

    def status_payload(self) -> dict:
        return {
            "database": self.name,
            "status": self.status.value,
            **({"reason": self.reason} if self.reason else {}),
            **({"latency_ms": self.latency_ms} if self.latency_ms is not None else {}),
        }
