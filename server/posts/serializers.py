"""
DRF serializers for Cassandra-backed post/comment/like resources.

Uses plain Serializer (not ModelSerializer) because the data lives in
Cassandra cqlengine models, not Django ORM models.
"""

from rest_framework import serializers


class PostSerializer(serializers.Serializer):
    """Read serializer for a post."""

    post_id = serializers.UUIDField(read_only=True)
    author_id = serializers.IntegerField(read_only=True)
    author_display_name = serializers.CharField(read_only=True)
    author_avatar_url = serializers.CharField(read_only=True, allow_null=True)
    title = serializers.CharField(max_length=255)
    content = serializers.CharField()
    image_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    geolocation = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    hashtags = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    like_count = serializers.IntegerField(read_only=True, default=0)
    is_liked = serializers.BooleanField(read_only=True, default=False)
    create_time = serializers.DateTimeField(read_only=True)
    update_time = serializers.DateTimeField(read_only=True)


class PostCreateSerializer(serializers.Serializer):
    """Write serializer for creating / updating a post."""

    title = serializers.CharField(max_length=255)
    content = serializers.CharField()
    image_url = serializers.ImageField(required=False, allow_null=True)
    geolocation = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    hashtags = serializers.CharField(required=False, default="[]", help_text="JSON-encoded list of hashtag strings")


class CommentSerializer(serializers.Serializer):
    """Read serializer for a comment."""

    comment_id = serializers.UUIDField(read_only=True)
    post_id = serializers.UUIDField(read_only=True)
    author_id = serializers.IntegerField(read_only=True)
    author_display_name = serializers.CharField(read_only=True)
    author_avatar_url = serializers.CharField(read_only=True, allow_null=True)
    content = serializers.CharField()
    parent_id = serializers.UUIDField(read_only=True, allow_null=True)
    create_time = serializers.DateTimeField(read_only=True)
    replies = serializers.ListField(read_only=True, default=list)


class CommentCreateSerializer(serializers.Serializer):
    """Write serializer for creating a comment."""

    content = serializers.CharField()
    parent_id = serializers.UUIDField(required=False, allow_null=True)


class TimelineSerializer(serializers.Serializer):
    """Lightweight serializer for feed timeline entries."""

    post_id = serializers.UUIDField(read_only=True)
    author_id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    content_preview = serializers.CharField(read_only=True)
    image_url = serializers.CharField(read_only=True, allow_null=True)
    create_time = serializers.DateTimeField(read_only=True)
