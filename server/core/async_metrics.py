"""Prometheus metrics for asynchronous workers and the outbox relay."""

from __future__ import annotations

import logging
import os
import threading

from prometheus_client import Counter, Gauge, Histogram, start_http_server


logger = logging.getLogger("terrierconnect.async_metrics")

_server_lock = threading.Lock()
_server_started = False


OUTBOX_EVENTS_TOTAL = Counter(
    "terrier_async_outbox_events_total",
    "Total number of outbox relay events handled.",
    labelnames=("topic", "result"),
)

OUTBOX_EVENT_PROCESSING_SECONDS = Histogram(
    "terrier_async_outbox_event_processing_seconds",
    "Time spent relaying outbox events into Kafka.",
    labelnames=("topic", "result"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

OUTBOX_PENDING_EVENTS = Gauge(
    "terrier_async_outbox_pending_events",
    "Current number of pending events in the Cassandra projection outbox.",
)

OUTBOX_OLDEST_EVENT_AGE_SECONDS = Gauge(
    "terrier_async_outbox_oldest_event_age_seconds",
    "Age in seconds of the oldest pending event in the Cassandra projection outbox.",
)

OUTBOX_RETRIES_TOTAL = Counter(
    "terrier_async_outbox_retries_total",
    "Total number of outbox relay retries after a failed publish attempt.",
    labelnames=("topic",),
)

CONSUMER_EVENTS_TOTAL = Counter(
    "terrier_async_consumer_events_total",
    "Total number of async events processed by consumer workers.",
    labelnames=("consumer", "topic", "result"),
)

CONSUMER_EVENT_PROCESSING_SECONDS = Histogram(
    "terrier_async_consumer_event_processing_seconds",
    "Time spent processing async events in consumer workers.",
    labelnames=("consumer", "topic", "result"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

CONSUMER_EVENT_AGE_SECONDS = Histogram(
    "terrier_async_consumer_event_age_seconds",
    "Age in seconds of an event when a consumer begins processing it.",
    labelnames=("consumer", "topic"),
    buckets=(0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),
)

CONSUMER_EVENTS_IN_PROGRESS = Gauge(
    "terrier_async_consumer_events_in_progress",
    "Number of consumer events currently being processed.",
    labelnames=("consumer",),
)

KAFKA_CONNECT_UP = Gauge(
    "terrier_kafka_connect_up",
    "Whether Kafka Connect status polling succeeded in the last scrape interval.",
)

KAFKA_CONNECT_CONNECTOR_STATE = Gauge(
    "terrier_kafka_connect_connector_state",
    "One-hot status for each Kafka Connect connector.",
    labelnames=("connector", "state"),
)

KAFKA_CONNECT_CONNECTOR_TASKS = Gauge(
    "terrier_kafka_connect_connector_tasks",
    "Number of Kafka Connect tasks in a given state for a connector.",
    labelnames=("connector", "state"),
)

KAFKA_CONNECT_DLQ_RECORDS = Gauge(
    "terrier_kafka_connect_dlq_records",
    "Approximate retained records in Kafka Connect dead-letter topics based on topic offsets.",
    labelnames=("topic",),
)


def start_metrics_http_server() -> None:
    """Start a lightweight Prometheus HTTP exporter for worker processes."""

    global _server_started

    if os.getenv("ASYNC_METRICS_ENABLED", "1") != "1":
        return

    host = os.getenv("ASYNC_METRICS_HOST", "0.0.0.0")
    port = int(os.getenv("ASYNC_METRICS_PORT", "9100"))

    with _server_lock:
        if _server_started:
            return
        try:
            start_http_server(port, addr=host)
        except OSError:
            logger.exception("Async metrics exporter failed to start on %s:%s", host, port)
            return

        _server_started = True
        logger.info("Async metrics exporter listening on %s:%s", host, port)


def observe_outbox_backlog(*, pending_events: int, oldest_age_seconds: float | None) -> None:
    OUTBOX_PENDING_EVENTS.set(max(0, pending_events))
    OUTBOX_OLDEST_EVENT_AGE_SECONDS.set(max(0.0, oldest_age_seconds or 0.0))


def observe_outbox_result(*, topic: str, result: str, duration_seconds: float) -> None:
    OUTBOX_EVENTS_TOTAL.labels(topic=topic, result=result).inc()
    OUTBOX_EVENT_PROCESSING_SECONDS.labels(topic=topic, result=result).observe(max(0.0, duration_seconds))


def observe_outbox_retry(*, topic: str) -> None:
    OUTBOX_RETRIES_TOTAL.labels(topic=topic).inc()


def observe_consumer_result(
    *,
    consumer: str,
    topic: str,
    result: str,
    duration_seconds: float,
    message_age_seconds: float | None = None,
) -> None:
    CONSUMER_EVENTS_TOTAL.labels(consumer=consumer, topic=topic, result=result).inc()
    CONSUMER_EVENT_PROCESSING_SECONDS.labels(
        consumer=consumer,
        topic=topic,
        result=result,
    ).observe(max(0.0, duration_seconds))
    if message_age_seconds is not None:
        CONSUMER_EVENT_AGE_SECONDS.labels(consumer=consumer, topic=topic).observe(
            max(0.0, message_age_seconds)
        )


def inc_consumer_in_progress(*, consumer: str) -> None:
    CONSUMER_EVENTS_IN_PROGRESS.labels(consumer=consumer).inc()


def dec_consumer_in_progress(*, consumer: str) -> None:
    CONSUMER_EVENTS_IN_PROGRESS.labels(consumer=consumer).dec()


def set_kafka_connect_up(is_up: bool) -> None:
    KAFKA_CONNECT_UP.set(1 if is_up else 0)


def set_kafka_connect_connector_state(*, connector: str, state: str, value: float) -> None:
    KAFKA_CONNECT_CONNECTOR_STATE.labels(connector=connector, state=state).set(value)


def set_kafka_connect_connector_tasks(*, connector: str, state: str, count: float) -> None:
    KAFKA_CONNECT_CONNECTOR_TASKS.labels(connector=connector, state=state).set(count)


def set_kafka_connect_dlq_records(*, topic: str, count: float) -> None:
    KAFKA_CONNECT_DLQ_RECORDS.labels(topic=topic).set(max(0.0, count))