"""
Cassandra models for the notifications system.

Notifications are written by Kafka consumers (notification consumer)
and read by the API. CDC does NOT capture this table (derived data).
"""

import uuid

from cassandra.cqlengine import columns
from cassandra.cqlengine.models import Model
from django.conf import settings


class NotificationsByUser(Model):
    """
    Partition: user_id (the recipient).
    Clustering: create_time DESC, notification_id for uniqueness.
    """
    __keyspace__ = None  # set dynamically below
    __table_name__ = "notifications_by_user"

    user_id = columns.Integer(partition_key=True)
    create_time = columns.DateTime(clustering_order="DESC", primary_key=True)
    notification_id = columns.UUID(primary_key=True, default=uuid.uuid4)

    # Notification data
    type = columns.Text()          # "like", "comment", "follow"
    actor_id = columns.Integer()
    actor_display_name = columns.Text()
    actor_avatar_url = columns.Text()
    target_id = columns.Text()     # post_id or user_id (as string)
    target_type = columns.Text()   # "post", "user"
    message = columns.Text()       # human-readable summary
    is_read = columns.Boolean(default=False)


# Dynamically set keyspace from settings
NotificationsByUser.__keyspace__ = getattr(settings, "CASSANDRA_KEYSPACE", "terrier")
