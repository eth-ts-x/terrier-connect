"""Poll Kafka Connect and DLQ topics, exposing Prometheus metrics for connector health."""

from __future__ import annotations

import json
import logging
import signal
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from confluent_kafka import Consumer, KafkaException, TopicPartition
from django.conf import settings
from django.core.management.base import BaseCommand

from core.async_metrics import (
    set_kafka_connect_connector_state,
    set_kafka_connect_connector_tasks,
    set_kafka_connect_dlq_records,
    set_kafka_connect_up,
    start_metrics_http_server,
)


logger = logging.getLogger("terrierconnect.connect_monitor")

CONNECTOR_STATES = ("RUNNING", "PAUSED", "FAILED", "UNASSIGNED", "RESTARTING", "DESTROYED")
TASK_STATES = ("RUNNING", "PAUSED", "FAILED", "UNASSIGNED", "DESTROYED")


class Command(BaseCommand):
    help = "Run the Kafka Connect and DLQ metrics monitor."

    def add_arguments(self, parser):
        parser.add_argument("--poll-interval", type=float, default=30.0, help="Seconds between Kafka Connect polls")

    def handle(self, *args, **options):
        start_metrics_http_server()

        connect_url = getattr(settings, "KAFKA_CONNECT_URL", "").rstrip("/")
        if not connect_url:
            raise SystemExit("KAFKA_CONNECT_URL must be configured for run_connect_monitor")

        poll_interval = max(5.0, float(options["poll_interval"]))
        dlq_topics = tuple(
            topic
            for topic in getattr(settings, "KAFKA_CONNECT_DLQ_TOPICS", [])
            if isinstance(topic, str) and topic.strip()
        )

        consumer = Consumer(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "group.id": "tc-connect-monitor",
                "enable.auto.commit": False,
                "socket.timeout.ms": 5000,
                "session.timeout.ms": 6000,
                "default.topic.config": {"auto.offset.reset": "latest"},
            }
        )

        running = True
        known_connectors: set[str] = set()
        known_dlq_topics: set[str] = set(dlq_topics)

        def _shutdown(signum, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        self.stdout.write(
            f"Kafka Connect monitor started (url={connect_url}, dlq_topics={list(dlq_topics)})"
        )

        try:
            while running:
                try:
                    connector_names = self._fetch_connector_names(connect_url)
                    set_kafka_connect_up(True)
                    self._update_connector_metrics(connect_url, connector_names, known_connectors)
                    self._update_dlq_metrics(consumer, known_dlq_topics)
                except Exception:
                    set_kafka_connect_up(False)
                    logger.exception("Kafka Connect monitor poll failed")

                time.sleep(poll_interval)
        finally:
            consumer.close()

        self.stdout.write(self.style.SUCCESS("Kafka Connect monitor stopped."))

    def _fetch_json(self, url: str):
        with urlopen(url, timeout=10) as response:  # nosec: internal service URL
            return json.loads(response.read().decode("utf-8"))

    def _fetch_connector_names(self, connect_url: str) -> list[str]:
        payload = self._fetch_json(f"{connect_url}/connectors")
        if not isinstance(payload, list):
            raise ValueError("Kafka Connect connectors response was not a list")
        return [str(item) for item in payload if isinstance(item, str)]

    def _update_connector_metrics(
        self,
        connect_url: str,
        connector_names: list[str],
        known_connectors: set[str],
    ) -> None:
        active_connectors = set(connector_names)
        all_connectors = sorted(known_connectors | active_connectors)

        for connector in all_connectors:
            status_payload = {}
            if connector in active_connectors:
                status_payload = self._fetch_json(f"{connect_url}/connectors/{connector}/status")

            connector_state = str(
                ((status_payload.get("connector") or {}).get("state")) if status_payload else "UNASSIGNED"
            ).upper()
            task_state_counts = {state: 0 for state in TASK_STATES}

            if status_payload:
                for task in status_payload.get("tasks", []):
                    task_state = str(task.get("state", "UNASSIGNED")).upper()
                    if task_state not in task_state_counts:
                        task_state_counts[task_state] = 0
                    task_state_counts[task_state] += 1

            for state in CONNECTOR_STATES:
                set_kafka_connect_connector_state(
                    connector=connector,
                    state=state,
                    value=1.0 if connector_state == state else 0.0,
                )

            for state in sorted(set(TASK_STATES) | set(task_state_counts.keys())):
                set_kafka_connect_connector_tasks(
                    connector=connector,
                    state=state,
                    count=float(task_state_counts.get(state, 0)),
                )

        known_connectors.clear()
        known_connectors.update(active_connectors)

    def _update_dlq_metrics(self, consumer: Consumer, known_dlq_topics: set[str]) -> None:
        for topic in sorted(known_dlq_topics):
            record_count = 0.0
            try:
                metadata = consumer.list_topics(topic=topic, timeout=5)
                topic_metadata = metadata.topics.get(topic)
                if topic_metadata is None or topic_metadata.error is not None:
                    set_kafka_connect_dlq_records(topic=topic, count=0.0)
                    continue

                for partition_id in topic_metadata.partitions.keys():
                    low, high = consumer.get_watermark_offsets(
                        TopicPartition(topic, partition_id),
                        timeout=5,
                        cached=False,
                    )
                    record_count += max(0, high - low)
            except (KafkaException, RuntimeError):
                logger.exception("Failed to inspect DLQ topic offsets for %s", topic)
                continue

            set_kafka_connect_dlq_records(topic=topic, count=record_count)