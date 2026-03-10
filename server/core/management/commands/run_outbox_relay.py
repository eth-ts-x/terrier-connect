"""Relay queued projection outbox events from Cassandra into Kafka."""

from __future__ import annotations

import json
import logging
import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from core.cassandra_models import ProjectionOutbox
from core.kafka_producer import send_event_sync


logger = logging.getLogger("terrierconnect.outbox")


class Command(BaseCommand):
    help = "Run the Cassandra projection outbox relay worker."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=50, help="Max events per shard to process per poll")
        parser.add_argument("--poll-interval", type=float, default=2.0, help="Sleep time when no work is found")
        parser.add_argument("--once", action="store_true", help="Process available work once and exit")

    def handle(self, *args, **options):
        shard_count = max(1, int(getattr(settings, "PROJECTION_OUTBOX_SHARDS", 4)))
        batch_size = max(1, int(options["batch_size"]))
        poll_interval = max(0.1, float(options["poll_interval"]))
        run_once = bool(options["once"])

        running = True

        def _shutdown(signum, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        self.stdout.write(
            f"Projection outbox relay started (shards={shard_count}, batch_size={batch_size}, once={run_once})"
        )

        while running:
            processed = 0
            for shard in range(shard_count):
                rows = list(ProjectionOutbox.objects.filter(shard=shard).limit(batch_size))
                for row in rows:
                    try:
                        send_event_sync(
                            topic=row.topic,
                            key=row.event_key,
                            payload=json.loads(row.payload),
                        )
                        ProjectionOutbox.objects(
                            shard=row.shard,
                            queued_at=row.queued_at,
                            event_id=row.event_id,
                        ).delete()
                        processed += 1
                    except Exception as exc:
                        logger.exception("Outbox relay failed for event=%s topic=%s", row.event_id, row.topic)
                        ProjectionOutbox.objects(
                            shard=row.shard,
                            queued_at=row.queued_at,
                            event_id=row.event_id,
                        ).update(
                            attempts=(row.attempts or 0) + 1,
                            last_error=str(exc)[:1000],
                        )

            if run_once:
                break

            if processed == 0:
                time.sleep(poll_interval)

        self.stdout.write(self.style.SUCCESS("Projection outbox relay stopped."))