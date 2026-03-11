"""
Singleton Kafka producer using confluent-kafka.

Configured with idempotent delivery (acks=all, enable.idempotence=true)
to guarantee at-least-once semantics with dedup at the broker level.
"""

import atexit
import json
import logging
from typing import Any, Mapping, Sequence

from django.conf import settings
from opentelemetry import trace
from opentelemetry.trace import SpanKind

from .async_tracing import encode_kafka_headers

logger = logging.getLogger("terrierconnect.kafka")
tracer = trace.get_tracer(__name__)

_producer = None


def _get_producer():
    global _producer
    if _producer is not None:
        return _producer

    try:
        from confluent_kafka import Producer

        _producer = Producer(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "enable.idempotence": True,
                "acks": "all",
                "retries": 2147483647,  # MAX_INT
                "max.in.flight.requests.per.connection": 5,
                "linger.ms": 5,
                "compression.type": "lz4",
            }
        )
        logger.info("Kafka producer initialised: %s", settings.KAFKA_BOOTSTRAP_SERVERS)
    except Exception:
        logger.warning("Kafka producer unavailable — events will be dropped", exc_info=True)
    return _producer


def _delivery_callback(err, msg):
    if err:
        logger.error("Kafka delivery failed: %s", err)
    else:
        logger.debug("Kafka delivered: topic=%s partition=%s", msg.topic(), msg.partition())


def flush_events(timeout: float = 5.0):
    producer = _get_producer()
    if producer is None:
        return 0

    remaining = producer.flush(timeout)
    if remaining:
        logger.warning("Kafka flush timed out with %d message(s) still pending", remaining)
    return remaining


def send_event(
    topic: str,
    key: str,
    payload: dict,
    *,
    headers: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
):
    """
    Publish a JSON event to Kafka. Non-blocking (buffered).
    Call flush() at process shutdown to ensure delivery.
    """
    producer = _get_producer()
    if producer is None:
        logger.warning("Kafka unavailable — dropping event topic=%s key=%s", topic, key)
        return

    with tracer.start_as_current_span(
        f"kafka publish {topic}",
        kind=SpanKind.PRODUCER,
        attributes={
            "messaging.system": "kafka",
            "messaging.destination.name": topic,
            "messaging.operation": "publish",
        },
    ):
        producer.produce(
            topic=topic,
            key=key.encode("utf-8") if isinstance(key, str) else key,
            value=json.dumps(payload, default=str).encode("utf-8"),
            headers=encode_kafka_headers(headers),
            callback=_delivery_callback,
        )
        producer.poll(0)  # trigger callback delivery


def send_event_sync(
    topic: str,
    key: str,
    payload: dict,
    timeout: float = 5.0,
    *,
    headers: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
):
    """Publish a JSON event to Kafka and wait for broker acknowledgement."""
    producer = _get_producer()
    if producer is None:
        raise RuntimeError(f"Kafka unavailable for topic={topic}")

    errors: list[str] = []

    def _sync_callback(err, msg):
        if err:
            errors.append(str(err))
            logger.error("Kafka delivery failed: %s", err)
        else:
            logger.debug("Kafka delivered: topic=%s partition=%s", msg.topic(), msg.partition())

    with tracer.start_as_current_span(
        f"kafka publish {topic}",
        kind=SpanKind.PRODUCER,
        attributes={
            "messaging.system": "kafka",
            "messaging.destination.name": topic,
            "messaging.operation": "publish",
        },
    ):
        producer.produce(
            topic=topic,
            key=key.encode("utf-8") if isinstance(key, str) else key,
            value=json.dumps(payload, default=str).encode("utf-8"),
            headers=encode_kafka_headers(headers),
            callback=_sync_callback,
        )
        producer.poll(0)
        remaining = flush_events(timeout)
        if remaining:
            raise RuntimeError(f"Kafka flush timed out with {remaining} pending message(s)")
        if errors:
            raise RuntimeError(errors[0])


atexit.register(flush_events)
