"""OpenTelemetry tracing bootstrap for Django workloads."""

from __future__ import annotations

import logging
import os
from typing import Mapping

import google.auth
from google.auth.transport.requests import AuthorizedSession
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF, ALWAYS_ON, ParentBased, TraceIdRatioBased


logger = logging.getLogger(__name__)

_INITIALIZED = False


def initialize_telemetry() -> None:
    """Configure OpenTelemetry tracing once per process."""

    global _INITIALIZED

    if _INITIALIZED:
        return
    _INITIALIZED = True

    if not _is_enabled("OTEL_TRACES_ENABLED", default=False):
        return

    exporter = _build_trace_exporter()
    if exporter is None:
        logger.info("OpenTelemetry tracing enabled but no trace exporter is configured")
        return

    provider = TracerProvider(
        resource=_build_resource(),
        sampler=_build_sampler(),
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    DjangoInstrumentor().instrument(excluded_urls="^/metrics$,^/api/posts/health/$")

    try:
        RedisInstrumentor().instrument()
    except Exception:
        logger.exception("Failed to instrument Redis with OpenTelemetry")


def _build_resource() -> Resource:
    attributes = {
        "service.name": os.getenv("SERVICE_NAME", "terrier-connect-server"),
        "service.version": os.getenv("SERVICE_VERSION", ""),
        "deployment.environment": os.getenv("APP_ENV", "development"),
    }

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    if project_id:
        attributes["gcp.project_id"] = project_id

    return Resource.create(attributes)


def _build_sampler():
    sampler_name = os.getenv("OTEL_TRACES_SAMPLER", "parentbased_traceidratio").strip().lower()
    sampler_arg = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "1.0"))

    if sampler_name == "always_off":
        return ALWAYS_OFF
    if sampler_name == "always_on":
        return ALWAYS_ON
    if sampler_name == "traceidratio":
        return TraceIdRatioBased(sampler_arg)
    return ParentBased(TraceIdRatioBased(sampler_arg))


def _build_trace_exporter() -> OTLPSpanExporter | None:
    endpoint = _resolve_traces_endpoint()
    if not endpoint:
        return None

    headers = _parse_headers(os.getenv("OTEL_EXPORTER_OTLP_HEADERS", ""))
    timeout = float(os.getenv("OTEL_EXPORTER_OTLP_TIMEOUT", "10"))

    if _is_enabled("OTEL_EXPORTER_OTLP_GCP_AUTH", default=False):
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return OTLPSpanExporter(
            endpoint=endpoint,
            headers=headers or None,
            timeout=timeout,
            session=AuthorizedSession(credentials),
        )

    return OTLPSpanExporter(
        endpoint=endpoint,
        headers=headers or None,
        timeout=timeout,
    )


def _resolve_traces_endpoint() -> str:
    endpoint = (
        os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    )
    if not endpoint:
        return ""
    if endpoint.endswith("/v1/traces"):
        return endpoint
    return f"{endpoint.rstrip('/')}/v1/traces"


def _parse_headers(raw_headers: str) -> Mapping[str, str]:
    headers: dict[str, str] = {}
    for item in raw_headers.split(","):
        name, separator, value = item.partition("=")
        if separator and name.strip() and value.strip():
            headers[name.strip()] = value.strip()
    return headers


def _is_enabled(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}