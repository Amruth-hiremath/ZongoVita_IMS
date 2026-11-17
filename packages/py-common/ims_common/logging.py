"""Structured logging (AD-74; LLD section 16).

JSON lines carrying request_id, trace_id, customer code, principal, route, status and duration.
Business content must never reach the logs (no passwords, tokens, secrets, bodies, item names
or quantities). To make that the default rather than a convention, only fields on the allow-list
below are emitted from ``extra``; anything else passed by mistake is dropped.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("ims_request_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("ims_trace_id", default=None)
customer_code_var: ContextVar[str | None] = ContextVar("ims_customer_code", default=None)
principal_var: ContextVar[str | None] = ContextVar("ims_principal", default=None)

#: Operational fields that may be attached to a log record through ``extra``.
ALLOWED_EXTRA_FIELDS = frozenset(
    {
        "route",
        "method",
        "status",
        "duration_ms",
        "code",
        "kind",
        "attempt",
        "attempts",
        "job_type",
        "event_type",
        "feed_seq",
        "snapshot_age_s",
        "alarm",
        "sqlstate",
        "schema_version",
        "database_status",
        "count",
        "stage",
        "reason_code",
        "retry_in_s",
        "source",
    }
)


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str, instance: str) -> None:
        super().__init__()
        self._service = service
        self._instance = instance

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "service": self._service,
            "instance": self._instance,
            "msg": record.getMessage(),
        }
        for key, var in (
            ("request_id", request_id_var),
            ("trace_id", trace_id_var),
            ("customer", customer_code_var),
            ("principal", principal_var),
        ):
            value = var.get()
            if value is not None:
                entry[key] = value
        for key in ALLOWED_EXTRA_FIELDS:
            if key in record.__dict__:
                entry[key] = record.__dict__[key]
        if record.exc_info:
            # Type and location only. Exception messages can embed SQL parameters or payloads.
            exc_type = record.exc_info[0]
            entry["exc_type"] = exc_type.__name__ if exc_type else None
            entry["exc_trace"] = self._safe_trace(record)
        return json.dumps(entry, default=str)

    @staticmethod
    def _safe_trace(record: logging.LogRecord) -> list[str]:
        frames: list[str] = []
        tb = record.exc_info[2] if record.exc_info else None
        while tb is not None:
            code = tb.tb_frame.f_code
            frames.append(f"{code.co_filename}:{tb.tb_lineno} in {code.co_name}")
            tb = tb.tb_next
        return frames[-12:]


def configure_logging(service: str, instance: str, level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service, instance))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Access logs are produced by the request pipeline with the allow-listed fields instead.
    logging.getLogger("uvicorn.access").disabled = True
