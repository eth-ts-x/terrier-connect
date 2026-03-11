"""Helpers for propagating trace context across async messaging boundaries."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from opentelemetry import propagate
from opentelemetry.context import Context

from .observability import get_request_id


REQUEST_ID_HEADER = "x-request-id"


def capture_message_headers() -> dict[str, str]:
    """Capture the active trace context and correlation headers."""

    headers: dict[str, str] = {}
    propagate.inject(headers)

    request_id = get_request_id()
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id

    return headers


def normalize_message_headers(
    headers: Mapping[str, Any] | Sequence[tuple[str, Any]] | None,
) -> dict[str, str]:
    """Normalize mixed header inputs into a string dictionary."""

    if headers is None:
        return {}

    items = headers.items() if isinstance(headers, Mapping) else headers
    normalized: dict[str, str] = {}

    for name, value in items:
        header_name = str(name).strip()
        if not header_name:
            continue

        header_value = _decode_header_value(value)
        if header_value is None:
            continue
        normalized[header_name] = header_value

    return normalized


def prepare_outbound_headers(
    headers: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
) -> dict[str, str]:
    """Merge propagated headers with the current active span context."""

    outbound = normalize_message_headers(headers)
    propagate.inject(outbound)

    if REQUEST_ID_HEADER not in outbound:
        request_id = get_request_id()
        if request_id:
            outbound[REQUEST_ID_HEADER] = request_id

    return outbound


def encode_kafka_headers(
    headers: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
) -> list[tuple[str, bytes]]:
    """Encode headers for `confluent_kafka` production."""

    return [
        (name, value.encode("utf-8"))
        for name, value in prepare_outbound_headers(headers).items()
    ]


def serialize_message_headers(
    headers: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
) -> str:
    """Serialize message headers for durable outbox storage."""

    return json.dumps(normalize_message_headers(headers), sort_keys=True)


def deserialize_message_headers(raw_headers: str | None) -> dict[str, str]:
    """Deserialize durable outbox headers into a string dictionary."""

    if not raw_headers:
        return {}

    try:
        decoded = json.loads(raw_headers)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}

    if not isinstance(decoded, dict):
        return {}

    return normalize_message_headers(decoded)


def extract_context_from_headers(
    headers: Mapping[str, Any] | Sequence[tuple[str, Any]] | None,
) -> Context:
    """Restore an OpenTelemetry parent context from message headers."""

    return propagate.extract(normalize_message_headers(headers))


def get_request_id_from_headers(
    headers: Mapping[str, Any] | Sequence[tuple[str, Any]] | None,
) -> str | None:
    """Read the propagated request id from message headers."""

    return normalize_message_headers(headers).get(REQUEST_ID_HEADER)


def _decode_header_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.decode("utf-8", errors="ignore")
    if isinstance(value, str):
        return value
    return str(value)