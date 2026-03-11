"""Observability helpers for structured logging and request correlation."""

from __future__ import annotations

from datetime import datetime, timezone
import contextvars
import os

from opentelemetry import trace
from pythonjsonlogger import jsonlogger


_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)


def set_request_id(request_id: str | None) -> None:
    _request_id_var.set(request_id)


def clear_request_id() -> None:
    _request_id_var.set(None)


def get_request_id() -> str | None:
    return _request_id_var.get()


def get_trace_log_fields() -> dict[str, object]:
    """Return Cloud Logging trace correlation fields for the active span."""

    span = trace.get_current_span()
    context = span.get_span_context()
    if not context.is_valid:
        return {}

    trace_id = f"{context.trace_id:032x}"
    span_id = f"{context.span_id:016x}"
    sampled = bool(context.trace_flags.sampled)

    fields: dict[str, object] = {
        "trace_id": trace_id,
        "span_id": span_id,
        "trace_sampled": sampled,
    }

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    if project_id:
        fields["logging.googleapis.com/trace"] = f"projects/{project_id}/traces/{trace_id}"
        fields["logging.googleapis.com/spanId"] = span_id
        fields["logging.googleapis.com/trace_sampled"] = sampled

    return fields


class CloudLoggingJsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter aligned with Cloud Logging structured log fields."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        log_record["timestamp"] = timestamp.replace("+00:00", "Z")
        log_record["severity"] = record.levelname
        log_record["message"] = record.getMessage()
        log_record["logger"] = record.name
        log_record["service"] = os.getenv("SERVICE_NAME", "terrier-connect-server")
        log_record["environment"] = os.getenv("APP_ENV", "development")

        service_version = os.getenv("SERVICE_VERSION", "")
        log_record["serviceContext"] = {
            "service": os.getenv("SERVICE_NAME", "terrier-connect-server"),
            **({"version": service_version} if service_version else {}),
        }

        request_id = getattr(record, "request_id", None) or get_request_id()
        if request_id:
            log_record["request_id"] = request_id

        log_record.update(get_trace_log_fields())

        log_record.pop("asctime", None)
        log_record.pop("levelname", None)
