"""Scheduled ingestion worker.

Runs as its own process (`python -m workers.sync_scheduler`, or the
`sync-worker` container) so long discovery fetches never block API requests.
Ticks once a minute and, on each tick:

  * runs every enabled source whose own `schedule_minutes` has elapsed
  * drains the retry queue (graph / persist stages that failed earlier)
  * flushes the buffered MonetDB analytics events

The worker is deliberately restartable and stateless: all progress lives in
MongoDB (`sources.last_run_at`, `ingestion_runs`, `ingestion_retry_queue`).
"""

from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if (_BACKEND / "app").is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.api.dependencies import AppState  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.databases import Databases  # noqa: E402

TICK_SECONDS = 60

logger = get_logger("nexora.worker")


class SyncScheduler:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.databases = Databases(self.settings)
        self.state: AppState | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        configure_logging(self.settings.debug)
        await self.databases.startup()

        if not self.settings.sync_enabled:
            logger.warning(
                "NEXORA_SYNC_ENABLED is false — worker is idle by configuration",
                event="sync_disabled",
            )

        while not self._stop.is_set():
            try:
                await self._ensure_state()
                if self.state is not None:
                    await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - a bad tick must not kill the worker
                logger.exception("sync tick failed", event="tick_error")
            await self._sleep(TICK_SECONDS)

        await self._shutdown()

    async def _ensure_state(self) -> None:
        """Build (or rebuild after a MongoDB outage) the shared wiring."""
        if self.state is not None:
            return
        try:
            self.state = AppState(self.settings, self.databases)
        except RuntimeError:
            logger.error(
                "MongoDB unreachable — worker idle until it recovers",
                event="worker_waiting_for_mongo",
            )
            await self.databases.mongo.health_check()
            return
        await self.state.ingestion.ensure_sources()
        logger.info(
            "Sync worker started",
            event="worker_started",
            interval_minutes=self.settings.sync_interval_minutes,
            sync_enabled=self.settings.sync_enabled,
        )

    async def tick(self) -> None:
        assert self.state is not None
        result = await self.state.ingestion.sync_all(
            triggered_by="scheduler", due_only=True
        )
        ran = result.get("ran") or []
        if ran:
            for run in ran:
                logger.info(
                    "source synced",
                    event="source_synced",
                    source=run.get("source_key"),
                    status=run.get("status"),
                    discovered=run.get("discovered"),
                    added=run.get("added"),
                    updated=run.get("updated"),
                    duplicates=run.get("duplicates_skipped"),
                    failures=run.get("failures"),
                )

        retries = await self.state.ingestion.process_retries()
        if retries.get("processed"):
            logger.info("retry queue drained", event="retries_processed", **retries)

        flushed = await self.state.analytics.flush()
        if flushed:
            logger.info("analytics flushed", event="analytics_flushed", count=flushed)

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    async def _shutdown(self) -> None:
        if self.state is not None:
            await self.state.close()
        await self.databases.shutdown()
        logger.info("Sync worker stopped", event="worker_stopped")

    def request_stop(self) -> None:
        logger.info("Shutdown requested", event="worker_stopping")
        self._stop.set()


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, scheduler: SyncScheduler) -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, scheduler.request_stop)
        except NotImplementedError:
            # Windows has no SIGTERM handler support in the event loop; the
            # KeyboardInterrupt path below covers Ctrl-C there.
            signal.signal(sig, lambda *_: scheduler.request_stop())


async def _main() -> int:
    scheduler = SyncScheduler()
    loop = asyncio.get_running_loop()
    _install_signal_handlers(loop, scheduler)
    await scheduler.start()
    return 0


def main() -> int:
    try:
        return asyncio.run(_main())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
