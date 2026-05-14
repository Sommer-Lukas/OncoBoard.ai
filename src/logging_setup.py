import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from src.config import get_settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extras = getattr(record, "extra_fields", None)
        if extras:
            payload.update(extras)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    _configured = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def log_agent_run(
    logger: logging.Logger,
    *,
    case_id: str,
    agent_name: str,
    duration_ms: int,
    status: str,
    tokens_used: int | None = None,
    error: str | None = None,
) -> None:
    fields: dict[str, Any] = {
        "event": "agent_run",
        "case_id": case_id,
        "agent_name": agent_name,
        "duration_ms": duration_ms,
        "status": status,
    }
    if tokens_used is not None:
        fields["tokens_used"] = tokens_used
    if error is not None:
        fields["error"] = error
    logger.info(f"{agent_name} {status}", extra={"extra_fields": fields})
