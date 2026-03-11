"""Queue projection events in Cassandra for durable asynchronous Kafka relay."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
import zlib

from cassandra.cqlengine.query import BatchQuery
from django.conf import settings

from .async_tracing import capture_message_headers, serialize_message_headers
from .cassandra_models import ProjectionOutbox


POST_TOPIC = "cassandra.terrier.post_by_id"
LIKE_TOPIC = "cassandra.terrier.likes_by_post"
COMMENT_TOPIC = "cassandra.terrier.comments_by_post"
FOLLOW_TOPIC = "postgres.public.users_userfollowrel"


def projections_enabled() -> bool:
    return bool(getattr(settings, "PROJECTION_EVENTS_ENABLED", False))


def _ts_ms(value: datetime | None = None) -> int:
    dt = value or datetime.utcnow()
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return int(dt.timestamp() * 1000)


def _serialize_key(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str, sort_keys=True)


def _outbox_shard(key: dict[str, Any]) -> int:
    shard_count = max(1, int(getattr(settings, "PROJECTION_OUTBOX_SHARDS", 4)))
    return zlib.crc32(_serialize_key(key).encode("utf-8")) % shard_count


def _emit(
    topic: str,
    key: dict[str, Any],
    payload: dict[str, Any],
    *,
    batch: BatchQuery | None = None,
) -> None:
    if not projections_enabled():
        return
    outbox = ProjectionOutbox.batch(batch) if batch is not None else ProjectionOutbox
    outbox.create(
        shard=_outbox_shard(key),
        queued_at=datetime.utcnow(),
        topic=topic,
        event_key=_serialize_key(key),
        payload=json.dumps(payload, default=str),
        headers=serialize_message_headers(capture_message_headers()),
        source=str(payload.get("__table", "") or ""),
        op=str(payload.get("__op", "") or ""),
        attempts=0,
        last_error="",
    )


def publish_post_event(*, op: str, post: Any, batch: BatchQuery | None = None) -> None:
    payload = {
        "post_id": str(post.post_id),
        "author_id": int(post.author_id),
        "author_display_name": getattr(post, "author_display_name", "") or "",
        "author_avatar_url": getattr(post, "author_avatar_url", "") or "",
        "title": getattr(post, "title", "") or "",
        "content": getattr(post, "content", "") or "",
        "image_url": getattr(post, "image_url", "") or "",
        "geolocation": getattr(post, "geolocation", "") or "",
        "hashtags": list(getattr(post, "hashtags", []) or []),
        "create_time": getattr(post, "create_time", datetime.utcnow()).isoformat(),
        "update_time": getattr(post, "update_time", getattr(post, "create_time", datetime.utcnow())).isoformat(),
        "__op": op,
        "__table": "post_by_id",
        "__source_ts_ms": _ts_ms(getattr(post, "update_time", None) or getattr(post, "create_time", None)),
        "__deleted": op == "d",
    }
    _emit(POST_TOPIC, {"post_id": str(post.post_id)}, payload, batch=batch)


def publish_like_event(
    *,
    op: str,
    post_id: Any,
    user_id: int,
    post_author_id: int,
    create_time: datetime | None = None,
    batch: BatchQuery | None = None,
) -> None:
    event_time = create_time or datetime.utcnow()
    payload = {
        "post_id": str(post_id),
        "user_id": int(user_id),
        "post_author_id": int(post_author_id),
        "create_time": event_time.isoformat(),
        "__op": op,
        "__table": "likes_by_post",
        "__source_ts_ms": _ts_ms(event_time),
        "__deleted": op == "d",
    }
    _emit(LIKE_TOPIC, {"post_id": str(post_id), "user_id": int(user_id)}, payload, batch=batch)


def publish_comment_event(
    *,
    op: str,
    post_id: Any,
    comment_id: Any,
    author_id: int,
    post_author_id: int,
    content: str,
    create_time: datetime,
    parent_id: Any = None,
    author_display_name: str = "",
    author_avatar_url: str | None = None,
    batch: BatchQuery | None = None,
) -> None:
    payload = {
        "post_id": str(post_id),
        "comment_id": str(comment_id),
        "author_id": int(author_id),
        "post_author_id": int(post_author_id),
        "content": content,
        "parent_id": str(parent_id) if parent_id else None,
        "author_display_name": author_display_name or "",
        "author_avatar_url": author_avatar_url or "",
        "create_time": create_time.isoformat(),
        "__op": op,
        "__table": "comments_by_post",
        "__source_ts_ms": _ts_ms(create_time),
        "__deleted": op == "d",
    }
    _emit(COMMENT_TOPIC, {"post_id": str(post_id), "comment_id": str(comment_id)}, payload, batch=batch)


def publish_follow_event(
    *,
    op: str,
    follower_id: int,
    following_id: int,
    created_time: datetime,
    batch: BatchQuery | None = None,
) -> None:
    payload = {
        "follower_id": int(follower_id),
        "following_id": int(following_id),
        "created_time": created_time.isoformat(),
        "__op": op,
        "__table": "users_userfollowrel",
        "__source_ts_ms": _ts_ms(created_time),
        "__deleted": op == "d",
    }
    _emit(
        FOLLOW_TOPIC,
        {"follower_id": int(follower_id), "following_id": int(following_id)},
        payload,
        batch=batch,
    )
