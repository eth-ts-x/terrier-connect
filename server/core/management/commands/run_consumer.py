"""
Management command: python manage.py run_consumer --consumer=<name>

Runs a Kafka consumer worker process.
Available consumers: feed_fanout, notification, like_counter
"""

import json
import logging
import signal
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger("terrierconnect.consumer")

CONSUMER_REGISTRY: dict = {}


def _register(name, topics):
    """Decorator to register a consumer handler."""
    def decorator(func):
        CONSUMER_REGISTRY[name] = {"topics": topics, "handler": func}
        return func
    return decorator


# ── Consumer handlers ───────────────────────────────────────────


@_register("feed_fanout", ["cassandra.terrier.post_by_id"])
def _handle_feed_fanout(key, value):
    """Fan out a new post to all of the author's followers' timelines."""
    from posts.cassandra_models import TimelineByUser
    from users.models import UserFollowRel
    import uuid as _uuid
    from datetime import datetime

    event = json.loads(value)
    after = event.get("after") or event  # Debezium CDC 'after' payload or raw

    author_id = after.get("author_id")
    post_id = after.get("post_id")
    if not author_id or not post_id:
        return

    follower_ids = UserFollowRel.objects.filter(
        following_id=author_id
    ).values_list("follower_id", flat=True)

    for fid in follower_ids:
        try:
            TimelineByUser.create(
                user_id=fid,
                create_time=datetime.fromisoformat(after.get("create_time", datetime.utcnow().isoformat())),
                post_id=_uuid.UUID(str(post_id)),
                author_id=author_id,
                title=after.get("title", ""),
                content_preview=after.get("content", "")[:200],
                image_url=after.get("image_url", ""),
            )
        except Exception:
            logger.exception("Feed fanout failed for follower=%s post=%s", fid, post_id)

    logger.info("Fan-out post=%s to %d followers", post_id, len(follower_ids))


@_register("notification", [
    "cassandra.terrier.likes_by_post",
    "cassandra.terrier.comments_by_post",
    "postgres.public.users_userfollowrel",
])
def _handle_notification(key, value):
    """Create a notification for likes, comments, and follows."""
    from notifications.cassandra_models import NotificationsByUser
    import uuid as _uuid
    from datetime import datetime

    event = json.loads(value)
    after = event.get("after") or event

    # Determine notification type from topic (embedded in event metadata)
    source_table = event.get("source", {}).get("table", "")

    if "likes" in source_table:
        ntype = "like"
        recipient_id = after.get("post_author_id")  # denormalised
        actor_id = after.get("user_id")
        target_id = str(after.get("post_id", ""))
        message = "liked your post"
    elif "comments" in source_table:
        ntype = "comment"
        recipient_id = after.get("post_author_id")
        actor_id = after.get("author_id")
        target_id = str(after.get("post_id", ""))
        message = "commented on your post"
    elif "follow" in source_table:
        ntype = "follow"
        recipient_id = after.get("following_id")
        actor_id = after.get("follower_id")
        target_id = str(actor_id)
        message = "started following you"
    else:
        return

    if not recipient_id or not actor_id or recipient_id == actor_id:
        return

    try:
        NotificationsByUser.create(
            user_id=recipient_id,
            notification_id=_uuid.uuid4(),
            create_time=datetime.utcnow(),
            notification_type=ntype,
            actor_id=actor_id,
            target_id=target_id,
            message=message,
            is_read=False,
        )
    except Exception:
        logger.exception("Notification creation failed")


@_register("like_counter", ["cassandra.terrier.likes_by_post"])
def _handle_like_counter(key, value):
    """Update the LikeCount counter table and invalidate Redis cache."""
    from posts.cassandra_models import LikeCount
    from django.core.cache import cache

    event = json.loads(value)
    after = event.get("after") or event
    post_id = after.get("post_id")
    if not post_id:
        return

    import uuid as _uuid

    post_uuid = _uuid.UUID(str(post_id))
    # Increment counter (Debezium doesn't tell us insert vs delete easily,
    # so we recount — acceptable at this scale)
    from posts.cassandra_models import LikesByPost

    count = LikesByPost.objects.filter(post_id=post_uuid).count()
    try:
        LikeCount.objects.filter(post_id=post_uuid).update(count=count)
    except Exception:
        LikeCount.create(post_id=post_uuid, count=count)

    cache.delete(f"post:{post_id}:like_count")
    logger.debug("Like count updated: post=%s count=%d", post_id, count)


# ── Command ──────────────────────────────────────────────────────


class Command(BaseCommand):
    help = "Run a Kafka consumer worker."

    def add_arguments(self, parser):
        parser.add_argument(
            "--consumer",
            required=True,
            choices=list(CONSUMER_REGISTRY.keys()),
            help="Consumer to run",
        )
        parser.add_argument("--group-suffix", default="", help="Consumer group suffix")

    def handle(self, *args, **options):
        name = options["consumer"]
        spec = CONSUMER_REGISTRY[name]

        from confluent_kafka import Consumer, KafkaError

        group_id = f"tc-{name}{options['group_suffix']}"
        consumer = Consumer(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
            }
        )
        consumer.subscribe(spec["topics"])
        self.stdout.write(f"Consumer '{name}' subscribed to {spec['topics']} (group={group_id})")
        self.stdout.write(
            f"NOTE: Topics may not exist yet until CDC / producers create them. "
            f"The consumer will wait and retry automatically."
        )

        running = True

        def _shutdown(signum, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        while running:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                if msg.error().code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
                    # Topic doesn't exist yet — CDC/producer hasn't created it
                    logger.debug("Topic not yet available: %s (will retry)", msg.error())
                    continue
                logger.error("Consumer error: %s", msg.error())
                continue

            try:
                spec["handler"](msg.key(), msg.value())
            except Exception:
                logger.exception("Consumer '%s' handler error", name)

        consumer.close()
        self.stdout.write(self.style.SUCCESS(f"Consumer '{name}' shut down."))
