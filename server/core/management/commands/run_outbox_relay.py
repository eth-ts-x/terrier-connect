"""Relay queued projection outbox events from Cassandra into Kafka."""

from __future__ import annotations

import json
import logging
import signal
import time
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from core.async_tracing import (
    deserialize_message_headers,
    extract_context_from_headers,
    get_request_id_from_headers,
)
from core.async_metrics import (
    observe_outbox_backlog,
    observe_outbox_result,
    observe_outbox_retry,
    start_metrics_http_server,
)
from core.cassandra_models import ProjectionOutbox
from core.kafka_producer import send_event_sync
from core.observability import clear_request_id, set_request_id


logger = logging.getLogger("terrierconnect.outbox")
tracer = trace.get_tracer(__name__)


class Command(BaseCommand):
    help = "Run the Cassandra projection outbox relay worker."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=50, help="Max events per shard to process per poll")
        parser.add_argument("--poll-interval", type=float, default=2.0, help="Sleep time when no work is found")
        parser.add_argument("--once", action="store_true", help="Process available work once and exit")

    def handle(self, *args, **options):
        start_metrics_http_server()

        shard_count = max(1, int(getattr(settings, "PROJECTION_OUTBOX_SHARDS", 4)))
        batch_size = max(1, int(options["batch_size"]))
        poll_interval = max(0.1, float(options["poll_interval"]))
        run_once = bool(options["once"])
        backlog_refresh_interval = max(5.0, poll_interval)

        running = True
        last_backlog_refresh = 0.0

        def _shutdown(signum, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        self.stdout.write(
            f"Projection outbox relay started (shards={shard_count}, batch_size={batch_size}, once={run_once})"
        )

        while running:
            if time.monotonic() - last_backlog_refresh >= backlog_refresh_interval:
                pending_events = 0
                oldest_queued_at = None

                for shard in range(shard_count):
                    pending_events += ProjectionOutbox.objects.filter(shard=shard).count()
                    oldest_in_shard = ProjectionOutbox.objects.filter(shard=shard).limit(1).first()
                    if oldest_in_shard and (
                        oldest_queued_at is None or oldest_in_shard.queued_at < oldest_queued_at
                    ):
                        oldest_queued_at = oldest_in_shard.queued_at

                oldest_age_seconds = None
                if oldest_queued_at is not None:
                    oldest_age_seconds = max(
                        0.0,
                        (datetime.utcnow() - oldest_queued_at).total_seconds(),
                    )

                observe_outbox_backlog(
                    pending_events=pending_events,
                    oldest_age_seconds=oldest_age_seconds,
                )
                last_backlog_refresh = time.monotonic()

            processed = 0
            for shard in range(shard_count):
                rows = list(ProjectionOutbox.objects.filter(shard=shard).limit(batch_size))
                for row in rows:
                    headers = deserialize_message_headers(getattr(row, "headers", None))
                    request_id = get_request_id_from_headers(headers)
                    started_at = time.perf_counter()
                    try:
                        with tracer.start_as_current_span(
                            "projection.outbox.relay",
                            context=extract_context_from_headers(headers),
                            kind=SpanKind.INTERNAL,
                            attributes={
                                "messaging.system": "kafka",
                                "messaging.destination.name": row.topic,
                                "messaging.operation": "relay",
                                "messaging.message.id": str(row.event_id),
                            },
                        ) as span:
                            if request_id:
                                set_request_id(request_id)

                            send_event_sync(
                                topic=row.topic,
                                key=row.event_key,
                                payload=json.loads(row.payload),
                                headers=headers,
                            )

                        ProjectionOutbox.objects(
                            shard=row.shard,
                            queued_at=row.queued_at,
                            event_id=row.event_id,
                        ).delete()
                        observe_outbox_result(
                            topic=row.topic,
                            result="success",
                            duration_seconds=time.perf_counter() - started_at,
                        )
                        processed += 1
                    except Exception as exc:
                        span = trace.get_current_span()
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
                        observe_outbox_retry(topic=row.topic)
                        observe_outbox_result(
                            topic=row.topic,
                            result="error",
                            duration_seconds=time.perf_counter() - started_at,
                        )
                        logger.exception("Outbox relay failed for event=%s topic=%s", row.event_id, row.topic)
                        ProjectionOutbox.objects(
                            shard=row.shard,
                            queued_at=row.queued_at,
                            event_id=row.event_id,
                        ).update(
                            attempts=(row.attempts or 0) + 1,
                            last_error=str(exc)[:1000],
                        )
                    finally:
                        clear_request_id()

            if run_once:
                break

            if processed == 0:
                time.sleep(poll_interval)

        self.stdout.write(self.style.SUCCESS("Projection outbox relay stopped."))