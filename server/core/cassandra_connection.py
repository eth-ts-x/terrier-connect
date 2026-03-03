"""
Initialise a cqlengine connection to Cassandra using Django settings.
Called once from CoreConfig.ready().
"""

import logging

from cassandra.cluster import Cluster
from cassandra.cqlengine import connection as cql_connection
from cassandra.cqlengine.management import sync_table, create_keyspace_simple
from cassandra.policies import DCAwareRoundRobinPolicy
from django.conf import settings

logger = logging.getLogger("terrierconnect.cassandra")

_connected = False


def connect_cassandra():
    """Idempotent — safe to call multiple times."""
    global _connected
    if _connected:
        return

    try:
        cluster = Cluster(
            contact_points=settings.CASSANDRA_HOSTS,
            port=settings.CASSANDRA_PORT,
            protocol_version=4,
            load_balancing_policy=DCAwareRoundRobinPolicy(
                local_dc="datacenter1",
            ),
        )
        session = cluster.connect()
        cql_connection.register_connection("default", session=session)
        cql_connection.set_default_connection("default")
        _connected = True
        logger.info(
            "Cassandra connected: hosts=%s keyspace=%s",
            settings.CASSANDRA_HOSTS,
            settings.CASSANDRA_KEYSPACE,
        )
    except Exception:
        logger.warning("Cassandra not available — skipping connection", exc_info=True)


def ensure_schema():
    """Create keyspace and sync all Cassandra tables. Idempotent."""
    from posts.cassandra_models import (
        PostById,
        PostsByUser,
        TimelineByUser,
        LikesByPost,
        LikesByUser,
        LikeCount,
        CommentsByPost,
    )
    from notifications.cassandra_models import NotificationsByUser

    repl = settings.CASSANDRA_REPLICATION
    create_keyspace_simple(
        settings.CASSANDRA_KEYSPACE,
        replication_factor=repl["replication_factor"],
        connections=["default"],
    )

    tables = [
        PostById,
        PostsByUser,
        TimelineByUser,
        LikesByPost,
        LikesByUser,
        LikeCount,
        CommentsByPost,
        NotificationsByUser,
    ]
    for model in tables:
        sync_table(model, keyspaces=[settings.CASSANDRA_KEYSPACE], connections=["default"])

    logger.info("Cassandra schema synced: %d tables", len(tables))
