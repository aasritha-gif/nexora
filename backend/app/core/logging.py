from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


_RESERVED = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Structured JSON logs — one object per line, ready for log shipping."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED and value is not None and key not in payload:
                payload[key] = value
        return json.dumps(payload, default=str)


class StructuredLogger(logging.LoggerAdapter):
    """Accepts keyword context on every call (`log.info("ev", user_id=x)`) and
    routes it into the record so JsonFormatter emits it as structured fields."""

    def process(self, msg, kwargs):
        extra = dict(kwargs.pop("extra", None) or {})
        moved = []
        for key, value in list(kwargs.items()):
            if key in ("exc_info", "stack_info", "stacklevel"):
                continue
            extra[key] = value
            moved.append(key)
        for key in moved:
            kwargs.pop(key, None)
        if extra:
            kwargs["extra"] = extra
        return msg, kwargs

    def log(self, level, msg, *args, **kwargs):
        if not self.isEnabledFor(level):
            return
        msg, kwargs = self.process(msg, kwargs)
        self.logger._log(level, msg, args, **kwargs)


def configure_logging(debug: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    for noisy in ("httpx", "httpcore", "urllib3", "motor", "pymongo"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # uvicorn installs its own handlers; hand them to the JSON formatter so the
    # process emits exactly one log format on one stream.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def get_logger(name: str) -> StructuredLogger:
    return StructuredLogger(logging.getLogger(name), {})


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def monotonic_ms() -> float:
    return time.monotonic() * 1000
