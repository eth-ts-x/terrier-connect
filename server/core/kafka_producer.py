"""
Singleton Kafka producer using confluent-kafka.

Configured with idempotent delivery (acks=all, enable.idempotence=true)
to guarantee at-least-once semantics with dedup at the broker level.
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger("terrierconnect.kafka")

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


def send_event(topic: str, key: str, payload: dict):
    """
    Publish a JSON event to Kafka. Non-blocking (buffered).
    Call flush() at process shutdown to ensure delivery.
    """
    producer = _get_producer()
    if producer is None:
        logger.warning("Kafka unavailable — dropping event topic=%s key=%s", topic, key)
        return

    producer.produce(
        topic=topic,
        key=key.encode("utf-8") if isinstance(key, str) else key,
        value=json.dumps(payload, default=str).encode("utf-8"),
        callback=_delivery_callback,
    )
    producer.poll(0)  # trigger callback delivery
