"""
Management command: python manage.py run_consumer --consumer=<name>

Runs a Kafka consumer worker process.
Available consumers: feed_fanout, notification, like_counter, search_indexer
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import signal
import uuid
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger("terrierconnect.consumer")

CONSUMER_REGISTRY: dict[str, dict[str, Any]] = {}


@dataclass(frozen=True)
class CDCMessage:
    topic: str
    key: dict[str, Any]
    payload: dict[str, Any]
    raw: dict[str, Any]
    op: str | None
    table: str | None
    source_ts_ms: int | None
    deleted: bool


def _json_loads(value):
    if value in (None, b"", ""):
        return {}
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    try:
        loaded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _get_table_name(topic: str, raw: dict[str, Any]) -> str:
    table = raw.get("__table") or raw.get("table")
    if isinstance(table, str) and table:
        return table

    source = raw.get("source")
    if isinstance(source, dict) and isinstance(source.get("table"), str):
        return source["table"]

    return topic.split(".")[-1]


def _build_message(topic: str, key, value) -> CDCMessage:
    raw = _json_loads(value)
    message_key = _json_loads(key)

    payload = raw.get("after") if isinstance(raw.get("after"), dict) else raw
    if not isinstance(payload, dict):
        payload = raw.get("before") if isinstance(raw.get("before"), dict) else {}

    op = raw.get("__op") or raw.get("op")
    ts_ms = raw.get("__source_ts_ms") or raw.get("source_ts_ms") or raw.get("ts_ms")
    source_ts_ms = int(ts_ms) if isinstance(ts_ms, (int, float, str)) and str(ts_ms).isdigit() else None
    deleted = raw.get("__deleted") in (True, "true") or op == "d"

    return CDCMessage(
        topic=topic,
        key=message_key,
        payload=payload,
        raw=raw,
        op=op if isinstance(op, str) else None,
        table=_get_table_name(topic, raw),
        source_ts_ms=source_ts_ms,
        deleted=deleted,
    )


def _parse_datetime(value) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.utcnow()
    else:
        return datetime.utcnow()

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _parse_uuid(value) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except (ValueError, TypeError, AttributeError):
        return None


def _parse_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _avatar_url(user) -> str | None:
    avatar = getattr(user, "avatar_url", None)
    if not avatar:
        return None
    try:
        return avatar.url
    except Exception:
        return None


def _string_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def _register(name, topics):
    """Decorator to register a consumer handler."""
    def decorator(func):
        CONSUMER_REGISTRY[name] = {"topics": topics, "handler": func}
        return func
    return decorator


# ── Consumer handlers ───────────────────────────────────────────


@_register("feed_fanout", ["cassandra.terrier.post_by_id"])
def _handle_feed_fanout(message: CDCMessage):
    """Project post mutations into follower timelines."""
    if message.deleted:
        operation = "delete"
    elif message.op in ("u", "r"):
        operation = "update"
    else:
        operation = "upsert"

    from posts.cassandra_models import TimelineByUser
    from users.models import UserFollowRel

    author_id = _parse_int(message.payload.get("author_id"))
    post_uuid = _parse_uuid(message.payload.get("post_id") or message.key.get("post_id"))
    create_time = _parse_datetime(message.payload.get("create_time"))
    if not author_id or not post_uuid:
        return

    follower_ids = UserFollowRel.objects.filter(
        following_id=author_id
    ).values_list("follower_id", flat=True)

    for fid in follower_ids:
        try:
            query = TimelineByUser.objects(
                user_id=fid,
                create_time=create_time,
                post_id=post_uuid,
            )
            existing = TimelineByUser.objects.filter(
                user_id=fid,
                create_time=create_time,
                post_id=post_uuid,
            ).first()

            if operation == "delete":
                if existing:
                    query.delete()
                continue

            payload = {
                "author_id": author_id,
                "title": message.payload.get("title", ""),
                "content_preview": str(message.payload.get("content", ""))[:200],
                "image_url": message.payload.get("image_url", ""),
            }

            if existing:
                query.update(**payload)
            else:
                TimelineByUser.create(
                    user_id=fid,
                    create_time=create_time,
                    post_id=post_uuid,
                    **payload,
                )
        except Exception:
            logger.exception("Feed fanout failed for follower=%s post=%s", fid, post_uuid)

    logger.info("Feed projection complete: op=%s post=%s followers=%d", operation, post_uuid, len(follower_ids))


@_register("notification", [
    "cassandra.terrier.likes_by_post",
    "cassandra.terrier.comments_by_post",
    "postgres.public.users_userfollowrel",
])
def _handle_notification(message: CDCMessage):
    """Project likes, comments, and follows into user notifications."""
    if message.deleted:
        return

    from notifications.cassandra_models import NotificationsByUser
    from django.contrib.auth import get_user_model

    User = get_user_model()
    source_table = (message.table or message.topic).lower()
    event_time = _parse_datetime(message.payload.get("create_time"))

    if "likes" in source_table:
        ntype = "like"
        recipient_id = _parse_int(message.payload.get("post_author_id"))
        actor_id = _parse_int(message.payload.get("user_id"))
        target_id = str(message.payload.get("post_id", ""))
        body_message = "liked your post"
        target_type = "post"
    elif "comments" in source_table:
        ntype = "comment"
        recipient_id = _parse_int(message.payload.get("post_author_id"))
        actor_id = _parse_int(message.payload.get("author_id"))
        target_id = str(message.payload.get("post_id", ""))
        body_message = "commented on your post"
        target_type = "post"
    elif "follow" in source_table:
        ntype = "follow"
        recipient_id = _parse_int(message.payload.get("following_id"))
        actor_id = _parse_int(message.payload.get("follower_id"))
        target_id = str(actor_id)
        body_message = "started following you"
        target_type = "user"
    else:
        return

    if not recipient_id or not actor_id or recipient_id == actor_id:
        return

    actor = User.objects.filter(id=actor_id).first()
    actor_display_name = getattr(actor, "display_name", None) or ""
    actor_avatar_url = _avatar_url(actor)
    notification_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"{message.topic}:{recipient_id}:{actor_id}:{target_id}:{message.source_ts_ms or int(event_time.timestamp() * 1000)}",
    )

    existing = NotificationsByUser.objects.filter(
        user_id=recipient_id,
        create_time=event_time,
        notification_id=notification_id,
    ).first()
    if existing:
        return

    try:
        NotificationsByUser.create(
            user_id=recipient_id,
            notification_id=notification_id,
            create_time=event_time,
            type=ntype,
            actor_id=actor_id,
            actor_display_name=actor_display_name,
            actor_avatar_url=actor_avatar_url,
            target_id=target_id,
            target_type=target_type,
            message=body_message,
            is_read=False,
        )
    except Exception:
        logger.exception("Notification creation failed")


@_register("like_counter", ["cassandra.terrier.likes_by_post"])
def _handle_like_counter(message: CDCMessage):
    """Project the materialized like counter from the source likes table."""
    from posts.cassandra_models import LikeCount
    from posts.cassandra_models import LikesByPost
    from django.core.cache import cache

    post_uuid = _parse_uuid(message.payload.get("post_id") or message.key.get("post_id"))
    user_id = _parse_int(message.payload.get("user_id") or message.key.get("user_id"))
    if not post_uuid:
        return

    count = LikesByPost.objects.filter(post_id=post_uuid).count()
    existing = LikeCount.objects.filter(post_id=post_uuid).first()
    if existing:
        LikeCount.objects(post_id=post_uuid).update(count=count)
    else:
        LikeCount.create(post_id=post_uuid, count=count)

    cache.delete(f"post:{post_uuid}:like_count")
    if user_id:
        cache.delete(f"post:{post_uuid}:liked:{user_id}")
    logger.debug("Like count projection updated: post=%s count=%d", post_uuid, count)


@_register("search_indexer", ["cassandra.terrier.post_by_id"])
def _handle_search_indexer(message: CDCMessage):
    """Project post mutations into Elasticsearch."""
    from core.elasticsearch_service import delete_post, index_post

    post_uuid = _parse_uuid(message.payload.get("post_id") or message.key.get("post_id"))
    if not post_uuid:
        return

    if message.deleted:
        delete_post(str(post_uuid))
        logger.info("Search projection deleted: post=%s", post_uuid)
        return

    index_post(
        {
            "post_id": str(post_uuid),
            "title": str(message.payload.get("title", "")),
            "content": str(message.payload.get("content", "")),
            "hashtags": _string_list(message.payload.get("hashtags")),
            "author_id": _parse_int(message.payload.get("author_id")) or 0,
            "author_display_name": str(message.payload.get("author_display_name", "")),
            "author_avatar_url": str(message.payload.get("author_avatar_url", "") or ""),
            "image_url": str(message.payload.get("image_url", "") or ""),
            "geolocation": str(message.payload.get("geolocation", "") or ""),
            "create_time": _parse_datetime(message.payload.get("create_time")).isoformat(),
            "update_time": _parse_datetime(
                message.payload.get("update_time") or message.payload.get("create_time")
            ).isoformat(),
        }
    )
    logger.info("Search projection indexed: post=%s", post_uuid)


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
                "enable.auto.commit": False,
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
                event = _build_message(msg.topic(), msg.key(), msg.value())
                spec["handler"](event)
                consumer.commit(message=msg, asynchronous=False)
            except Exception:
                logger.exception("Consumer '%s' handler error", name)

        consumer.close()
        self.stdout.write(self.style.SUCCESS(f"Consumer '{name}' shut down."))
