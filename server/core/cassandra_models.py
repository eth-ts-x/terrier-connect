"""Core Cassandra models shared across apps."""

import uuid
from datetime import datetime

from cassandra.cqlengine import columns
from cassandra.cqlengine.models import Model
from django.conf import settings


class ProjectionOutbox(Model):
    """Durable projection outbox for content events before Kafka publication."""

    __keyspace__ = getattr(settings, "CASSANDRA_KEYSPACE", "terrier")
    __table_name__ = "projection_outbox"

    shard = columns.Integer(primary_key=True, partition_key=True)
    queued_at = columns.DateTime(primary_key=True, clustering_order="ASC", default=datetime.utcnow)
    event_id = columns.UUID(primary_key=True, default=uuid.uuid4)

    topic = columns.Text(required=True)
    event_key = columns.Text(required=True)
    payload = columns.Text(required=True)
    source = columns.Text()
    op = columns.Text()
    attempts = columns.Integer(default=0)
    last_error = columns.Text(default="")