import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.context import correlation_id_var, program_id_var, user_id_var

_RESERVED_RECORD_KEYS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "asctime",
    "message",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Formats records as single-line JSON carrying the ERRLOG context columns."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=UTC)
        payload: dict[str, Any] = {
            "timestamp": timestamp.isoformat(),
            "process_date": timestamp.date().isoformat(),
            "process_time": timestamp.time().isoformat(),
            "level": record.levelname,
            "severity": _severity(record.levelno),
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
            "program_id": program_id_var.get(),
            "user_id": user_id_var.get(),
        }
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in _RESERVED_RECORD_KEYS
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _severity(levelno: int) -> int:
    """Map Python levels onto ERRLOG.ERROR_SEVERITY (1=Info, 2=Warning, 3=Error, 4=Severe)."""
    if levelno >= logging.CRITICAL:
        return 4
    if levelno >= logging.ERROR:
        return 3
    if levelno >= logging.WARNING:
        return 2
    return 1


def configure_logging(log_level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
