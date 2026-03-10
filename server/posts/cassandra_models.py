"""
Cassandra data models for posts, likes, comments, and timelines.

Uses cassandra-driver cqlengine directly (not django-cassandra-engine).
These are the source-of-truth tables for content data.
"""

import uuid
from datetime import datetime

from cassandra.cqlengine import columns
from cassandra.cqlengine.models import Model

from django.conf import settings

KEYSPACE = settings.CASSANDRA_KEYSPACE


# ── Source-of-truth tables (CDC-captured) ────────────────────────


class PostById(Model):
    """Single post lookup by ID. Source of truth for post content."""

    __keyspace__ = KEYSPACE
    __table_name__ = "post_by_id"

    post_id = columns.UUID(primary_key=True, default=uuid.uuid4)
    author_id = columns.Integer(required=True)
    author_display_name = columns.Text()
    author_avatar_url = columns.Text()
    title = columns.Text(required=True)
    content = columns.Text(required=True)
    image_url = columns.Text()
    geolocation = columns.Text()
    hashtags = columns.List(columns.Text)
    create_time = columns.DateTime(default=datetime.utcnow)
    update_time = columns.DateTime(default=datetime.utcnow)


class PostsByUser(Model):
    """All posts by a specific user, ordered newest first."""

    __keyspace__ = KEYSPACE
    __table_name__ = "posts_by_user"

    author_id = columns.Integer(primary_key=True, partition_key=True)
    create_time = columns.DateTime(primary_key=True, clustering_order="DESC")
    post_id = columns.UUID(primary_key=True)
    title = columns.Text()
    content = columns.Text()
    image_url = columns.Text()
    hashtags = columns.List(columns.Text)


class LikesByPost(Model):
    """Who liked a given post."""

    __keyspace__ = KEYSPACE
    __table_name__ = "likes_by_post"

    post_id = columns.UUID(primary_key=True, partition_key=True)
    user_id = columns.Integer(primary_key=True)
    post_author_id = columns.Integer()  # denormalised for notification consumer
    create_time = columns.DateTime(default=datetime.utcnow)


class LikesByUser(Model):
    """Posts a given user has liked."""

    __keyspace__ = KEYSPACE
    __table_name__ = "likes_by_user"

    user_id = columns.Integer(primary_key=True, partition_key=True)
    post_id = columns.UUID(primary_key=True)
    create_time = columns.DateTime(default=datetime.utcnow)


class LikeCount(Model):
    """Materialised like count per post."""

    __keyspace__ = KEYSPACE
    __table_name__ = "like_count"

    post_id = columns.UUID(primary_key=True)
    count = columns.Integer(default=0)


class CommentsByPost(Model):
    """Comments on a post, ordered by creation time."""

    __keyspace__ = KEYSPACE
    __table_name__ = "comments_by_post"

    post_id = columns.UUID(primary_key=True, partition_key=True)
    create_time = columns.DateTime(primary_key=True, clustering_order="ASC")
    comment_id = columns.UUID(primary_key=True, default=uuid.uuid4)
    author_id = columns.Integer(required=True)
    author_display_name = columns.Text()
    author_avatar_url = columns.Text()
    content = columns.Text(required=True)
    parent_id = columns.UUID()  # null for top-level comments
    post_author_id = columns.Integer()  # denormalised for notification consumer


# ── Derived tables (NOT CDC-captured — written by consumers) ─────


class TimelineByUser(Model):
    """Pre-computed feed for a user. Written by the feed fan-out consumer."""

    __keyspace__ = KEYSPACE
    __table_name__ = "timeline_by_user"

    user_id = columns.Integer(primary_key=True, partition_key=True)
    create_time = columns.DateTime(primary_key=True, clustering_order="DESC")
    post_id = columns.UUID(primary_key=True)
    author_id = columns.Integer()
    title = columns.Text()
    content_preview = columns.Text()
    image_url = columns.Text()
