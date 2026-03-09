"""
Post, Comment, Like API views.

Write path  → Cassandra (single write). Debezium CDC propagates to Kafka.
Read path   → Cassandra for feed/detail, Elasticsearch for search.
"""

import json
import logging
import uuid
from datetime import datetime
from types import SimpleNamespace

from cassandra.cqlengine.query import BatchQuery
from django.core.cache import cache
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .cassandra_models import (
    PostById,
    PostsByUser,
    TimelineByUser,
    LikesByPost,
    LikesByUser,
    LikeCount,
    CommentsByPost,
)
from .serializers import (
    PostSerializer,
    PostCreateSerializer,
    CommentSerializer,
    CommentCreateSerializer,
)
from hashtags.models import Hashtag
from core.projection_events import (
    publish_comment_event,
    publish_like_event,
    publish_post_event,
)

logger = logging.getLogger("terrierconnect.posts")


# ── Helpers ──────────────────────────────────────────────────────

def _paginate_cassandra(queryset, page_size: int = 10, cursor: str | None = None):
    """
    Simple limit-based pagination for Cassandra.
    Returns (items, next_cursor).
    """
    items = list(queryset.limit(page_size + 1))
    has_next = len(items) > page_size
    items = items[:page_size]
    next_cursor = str(items[-1].create_time.isoformat()) if has_next and items else None
    return items, next_cursor


def _post_to_dict(post) -> dict:
    """Convert a cqlengine model instance to a plain dict for serialization."""
    return {
        "post_id": post.post_id,
        "author_id": post.author_id,
        "author_display_name": getattr(post, "author_display_name", ""),
        "author_avatar_url": getattr(post, "author_avatar_url", None),
        "title": post.title,
        "content": post.content,
        "image_url": getattr(post, "image_url", None),
        "geolocation": getattr(post, "geolocation", None),
        "hashtags": list(getattr(post, "hashtags", []) or []),
        "create_time": post.create_time,
        "update_time": getattr(post, "update_time", post.create_time),
    }


def _enrich_like_info(posts_data: list[dict], user) -> list[dict]:
    """Inject like_count and is_liked into each post dict."""
    for p in posts_data:
        pid = p["post_id"]
        # Like count — cached
        cache_key = f"post:{pid}:like_count"
        count = cache.get(cache_key)
        if count is None:
            try:
                row = LikeCount.objects.filter(post_id=pid).first()
                count = row.count if row else 0
            except Exception:
                count = 0
            cache.set(cache_key, count, timeout=300)
        p["like_count"] = count

        # Is liked by current user
        if user and user.is_authenticated:
            liked_key = f"post:{pid}:liked:{user.id}"
            is_liked = cache.get(liked_key)
            if is_liked is None:
                try:
                    is_liked = LikesByPost.objects.filter(post_id=pid, user_id=user.id).first() is not None
                except Exception:
                    is_liked = False
                cache.set(liked_key, is_liked, timeout=300)
            p["is_liked"] = is_liked
        else:
            p["is_liked"] = False
    return posts_data


# ── Post ViewSet ─────────────────────────────────────────────────

class PostViewSet(viewsets.ViewSet):
    """
    CRUD for posts, feed, search, likes, and comments.
    All content data lives in Cassandra. Search uses Elasticsearch.
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "search", "by_tag", "comment_list"):
            return [AllowAny()]
        return [IsAuthenticated()]

    # ── LIST (feed) ──────────────────────────────────────────────

    def list(self, request):
        flag = request.query_params.get("flag", "all")
        page_size = int(request.query_params.get("pageSize", 10))

        if flag == "following":
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {"error": "Authentication required for following feed."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            qs = TimelineByUser.objects.filter(user_id=request.user.id)
            items, next_cursor = _paginate_cassandra(qs, page_size)
            # Timeline entries are lightweight — fetch full posts
            posts_data = []
            for item in items:
                cached = cache.get(f"post:{item.post_id}")
                if cached:
                    posts_data.append(cached)
                    continue
                post = PostById.objects.filter(post_id=item.post_id).first()
                if post:
                    d = _post_to_dict(post)
                    cache.set(f"post:{item.post_id}", d, timeout=600)
                    posts_data.append(d)
        else:
            # Latest posts — scan PostById (for small scale; production would
            # use a dedicated "latest posts" table partitioned by time bucket)
            qs = PostById.objects.all()
            items, next_cursor = _paginate_cassandra(qs, page_size)
            posts_data = [_post_to_dict(p) for p in items]

        posts_data = _enrich_like_info(posts_data, request.user)
        return Response({
            "results": PostSerializer(posts_data, many=True).data,
            "nextCursor": next_cursor,
        })

    # ── RETRIEVE ─────────────────────────────────────────────────

    def retrieve(self, request, pk=None):
        try:
            post_uuid = uuid.UUID(str(pk))
        except (ValueError, AttributeError):
            return Response({"error": "Invalid post ID."}, status=status.HTTP_400_BAD_REQUEST)

        cached = cache.get(f"post:{post_uuid}")
        if cached:
            data = cached
        else:
            post = PostById.objects.filter(post_id=post_uuid).first()
            if not post:
                return Response({"error": "Post not found."}, status=status.HTTP_404_NOT_FOUND)
            data = _post_to_dict(post)
            cache.set(f"post:{post_uuid}", data, timeout=600)

        data = _enrich_like_info([data], request.user)[0]
        return Response(PostSerializer(data).data)

    # ── CREATE ───────────────────────────────────────────────────

    def create(self, request):
        serializer = PostCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user

        # Parse hashtags
        try:
            hashtags = json.loads(data.get("hashtags", "[]"))
        except (json.JSONDecodeError, TypeError):
            hashtags = []

        # Handle image upload
        image_url = ""
        image_file = data.get("image_url")
        if image_file:
            from django.core.files.storage import default_storage
            path = default_storage.save(f"post_media/{image_file.name}", image_file)
            image_url = default_storage.url(path) if hasattr(default_storage, "url") else f"/media/{path}"

        now = datetime.utcnow()
        post_id = uuid.uuid4()
        author_avatar_url = user.avatar_url.url if user.avatar_url else ""
        result_model = SimpleNamespace(
            post_id=post_id,
            author_id=user.id,
            author_display_name=user.display_name or "",
            author_avatar_url=author_avatar_url,
            title=data["title"],
            content=data["content"],
            image_url=image_url,
            geolocation=data.get("geolocation", ""),
            hashtags=hashtags,
            create_time=now,
            update_time=now,
        )

        with BatchQuery() as batch:
            PostById.batch(batch).create(
                post_id=post_id,
                author_id=user.id,
                author_display_name=user.display_name or "",
                author_avatar_url=author_avatar_url,
                title=data["title"],
                content=data["content"],
                image_url=image_url,
                geolocation=data.get("geolocation", ""),
                hashtags=hashtags,
                create_time=now,
                update_time=now,
            )

            PostsByUser.batch(batch).create(
                author_id=user.id,
                create_time=now,
                post_id=post_id,
                title=data["title"],
                content=data["content"],
                image_url=image_url,
                hashtags=hashtags,
            )

            publish_post_event(op="c", post=result_model, batch=batch)

        # Ensure hashtag registry in PG (for trending/autocomplete)
        for tag in hashtags:
            Hashtag.objects.get_or_create(hashtag_text=tag)

        result = _post_to_dict(result_model)
        return Response(PostSerializer(result).data, status=status.HTTP_201_CREATED)

    # ── UPDATE ───────────────────────────────────────────────────

    def update(self, request, pk=None):
        try:
            post_uuid = uuid.UUID(str(pk))
        except (ValueError, AttributeError):
            return Response({"error": "Invalid post ID."}, status=status.HTTP_400_BAD_REQUEST)

        post = PostById.objects.filter(post_id=post_uuid).first()
        if not post or post.author_id != request.user.id:
            return Response({"error": "Post not found or not authorised."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PostCreateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            hashtags = json.loads(data.get("hashtags", "[]"))
        except (json.JSONDecodeError, TypeError):
            hashtags = list(post.hashtags or [])

        now = datetime.utcnow()
        merged_post = SimpleNamespace(
            post_id=post_uuid,
            author_id=post.author_id,
            author_display_name=getattr(post, "author_display_name", "") or "",
            author_avatar_url=getattr(post, "author_avatar_url", "") or "",
            title=data.get("title", post.title),
            content=data.get("content", post.content),
            image_url=getattr(post, "image_url", "") or "",
            geolocation=data.get("geolocation", getattr(post, "geolocation", "") or ""),
            hashtags=hashtags,
            create_time=post.create_time,
            update_time=now,
        )

        with BatchQuery() as batch:
            PostById.objects(post_id=post_uuid).batch(batch).update(
                title=merged_post.title,
                content=merged_post.content,
                hashtags=hashtags,
                geolocation=merged_post.geolocation,
                update_time=now,
            )
            PostsByUser.objects(
                author_id=post.author_id,
                create_time=post.create_time,
                post_id=post_uuid,
            ).batch(batch).update(
                title=merged_post.title,
                content=merged_post.content,
                image_url=merged_post.image_url,
                hashtags=hashtags,
            )
            publish_post_event(op="u", post=merged_post, batch=batch)

        cache.delete(f"post:{post_uuid}")
        result = _post_to_dict(merged_post)

        return Response(PostSerializer(result).data)

    # ── DESTROY ──────────────────────────────────────────────────

    def destroy(self, request, pk=None):
        try:
            post_uuid = uuid.UUID(str(pk))
        except (ValueError, AttributeError):
            return Response({"error": "Invalid post ID."}, status=status.HTTP_400_BAD_REQUEST)

        post = PostById.objects.filter(post_id=post_uuid).first()
        if not post or post.author_id != request.user.id:
            return Response({"error": "Post not found or not authorised."}, status=status.HTTP_404_NOT_FOUND)

        with BatchQuery() as batch:
            PostById.objects(post_id=post_uuid).batch(batch).delete()
            PostsByUser.objects(
                author_id=post.author_id,
                create_time=post.create_time,
                post_id=post_uuid,
            ).batch(batch).delete()
            publish_post_event(op="d", post=post, batch=batch)

        cache.delete(f"post:{post_uuid}")

        return Response({"message": "Post deleted."}, status=status.HTTP_204_NO_CONTENT)

    # ── SEARCH (Elasticsearch) ───────────────────────────────────

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def search(self, request):
        from core.elasticsearch_service import search_posts

        query = request.query_params.get("query", "")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("pageSize", 10))

        if not query:
            return Response({"error": "query parameter required."}, status=status.HTTP_400_BAD_REQUEST)

        result = search_posts(query, page=page, page_size=page_size)
        return Response({
            "total": result["total"],
            "page": page,
            "pageSize": page_size,
            "results": result["results"],
        })

    @action(detail=False, methods=["get"], url_path="by-tag", permission_classes=[AllowAny])
    def by_tag(self, request):
        from core.elasticsearch_service import search_by_hashtag

        tag = request.query_params.get("tag", "")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("pageSize", 10))

        if not tag:
            return Response({"error": "tag parameter required."}, status=status.HTTP_400_BAD_REQUEST)

        result = search_by_hashtag(tag, page=page, page_size=page_size)
        return Response({
            "total": result["total"],
            "page": page,
            "pageSize": page_size,
            "results": result["results"],
        })

    # ── LIKE / UNLIKE ────────────────────────────────────────────

    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        try:
            post_uuid = uuid.UUID(str(pk))
        except (ValueError, AttributeError):
            return Response({"error": "Invalid post ID."}, status=status.HTTP_400_BAD_REQUEST)

        post = PostById.objects.filter(post_id=post_uuid).first()
        if not post:
            return Response({"error": "Post not found."}, status=status.HTTP_404_NOT_FOUND)

        existing = LikesByPost.objects.filter(post_id=post_uuid, user_id=request.user.id).first()
        if existing:
            return Response({"error": "Already liked."}, status=status.HTTP_400_BAD_REQUEST)

        now = datetime.utcnow()
        with BatchQuery() as batch:
            LikesByPost.batch(batch).create(
                post_id=post_uuid,
                user_id=request.user.id,
                post_author_id=post.author_id,
                create_time=now,
            )
            LikesByUser.batch(batch).create(post_id=post_uuid, user_id=request.user.id, create_time=now)
            publish_like_event(
                op="c",
                post_id=post_uuid,
                user_id=request.user.id,
                post_author_id=post.author_id,
                create_time=now,
                batch=batch,
            )

        new_count = LikesByPost.objects.filter(post_id=post_uuid).count()

        cache.delete(f"post:{post_uuid}:like_count")
        cache.delete(f"post:{post_uuid}:liked:{request.user.id}")

        return Response({"liked": True, "like_count": new_count}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"])
    def unlike(self, request, pk=None):
        try:
            post_uuid = uuid.UUID(str(pk))
        except (ValueError, AttributeError):
            return Response({"error": "Invalid post ID."}, status=status.HTTP_400_BAD_REQUEST)

        existing = LikesByPost.objects.filter(post_id=post_uuid, user_id=request.user.id).first()
        if not existing:
            return Response({"error": "Not liked."}, status=status.HTTP_400_BAD_REQUEST)

        post = PostById.objects.filter(post_id=post_uuid).first()
        with BatchQuery() as batch:
            LikesByPost.objects(post_id=post_uuid, user_id=request.user.id).batch(batch).delete()
            LikesByUser.objects(user_id=request.user.id, post_id=post_uuid).batch(batch).delete()
            publish_like_event(
                op="d",
                post_id=post_uuid,
                user_id=request.user.id,
                post_author_id=post.author_id if post else existing.post_author_id,
                create_time=getattr(existing, "create_time", datetime.utcnow()),
                batch=batch,
            )

        new_count = LikesByPost.objects.filter(post_id=post_uuid).count()

        cache.delete(f"post:{post_uuid}:like_count")
        cache.delete(f"post:{post_uuid}:liked:{request.user.id}")

        return Response({"liked": False, "like_count": new_count})

    @action(detail=True, methods=["get"], url_path="like-status", permission_classes=[AllowAny])
    def like_status(self, request, pk=None):
        try:
            post_uuid = uuid.UUID(str(pk))
        except (ValueError, AttributeError):
            return Response({"error": "Invalid post ID."}, status=status.HTTP_400_BAD_REQUEST)

        count_key = f"post:{post_uuid}:like_count"
        count = cache.get(count_key)
        if count is None:
            row = LikeCount.objects.filter(post_id=post_uuid).first()
            count = row.count if row else 0
            cache.set(count_key, count, timeout=300)

        is_liked = False
        if request.user and request.user.is_authenticated:
            liked_key = f"post:{post_uuid}:liked:{request.user.id}"
            is_liked = cache.get(liked_key)
            if is_liked is None:
                is_liked = LikesByPost.objects.filter(post_id=post_uuid, user_id=request.user.id).first() is not None
                cache.set(liked_key, is_liked, timeout=300)

        return Response({"liked": is_liked, "like_count": count})

    # ── COMMENTS ─────────────────────────────────────────────────

    @action(detail=True, methods=["get"], url_path="comments", permission_classes=[AllowAny])
    def comment_list(self, request, pk=None):
        try:
            post_uuid = uuid.UUID(str(pk))
        except (ValueError, AttributeError):
            return Response({"error": "Invalid post ID."}, status=status.HTTP_400_BAD_REQUEST)

        page_size = int(request.query_params.get("pageSize", 50))
        comments = list(CommentsByPost.objects.filter(post_id=post_uuid).limit(page_size))

        # Build tree: top-level + replies
        top_level = []
        replies_map: dict[str, list] = {}
        for c in comments:
            c_dict = {
                "comment_id": c.comment_id,
                "post_id": c.post_id,
                "author_id": c.author_id,
                "author_display_name": c.author_display_name or "",
                "author_avatar_url": c.author_avatar_url,
                "content": c.content,
                "parent_id": c.parent_id,
                "create_time": c.create_time,
                "replies": [],
            }
            if c.parent_id:
                replies_map.setdefault(str(c.parent_id), []).append(c_dict)
            else:
                top_level.append(c_dict)

        for comment in top_level:
            comment["replies"] = replies_map.get(str(comment["comment_id"]), [])

        return Response({"results": CommentSerializer(top_level, many=True).data})

    @action(detail=True, methods=["post"], url_path="comments/add")
    def add_comment(self, request, pk=None):
        try:
            post_uuid = uuid.UUID(str(pk))
        except (ValueError, AttributeError):
            return Response({"error": "Invalid post ID."}, status=status.HTTP_400_BAD_REQUEST)

        post = PostById.objects.filter(post_id=post_uuid).first()
        if not post:
            return Response({"error": "Post not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = CommentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        now = datetime.utcnow()
        comment_id = uuid.uuid4()
        parent_id = serializer.validated_data.get("parent_id")

        with BatchQuery() as batch:
            CommentsByPost.batch(batch).create(
                post_id=post_uuid,
                create_time=now,
                comment_id=comment_id,
                author_id=user.id,
                author_display_name=user.display_name or "",
                author_avatar_url=user.avatar_url.url if user.avatar_url else "",
                content=serializer.validated_data["content"],
                parent_id=parent_id,
                post_author_id=post.author_id,
            )

            publish_comment_event(
                op="c",
                post_id=post_uuid,
                comment_id=comment_id,
                author_id=user.id,
                post_author_id=post.author_id,
                content=serializer.validated_data["content"],
                create_time=now,
                parent_id=parent_id,
                author_display_name=user.display_name or "",
                author_avatar_url=user.avatar_url.url if user.avatar_url else None,
                batch=batch,
            )

        return Response(
            CommentSerializer({
                "comment_id": comment_id,
                "post_id": post_uuid,
                "author_id": user.id,
                "author_display_name": user.display_name or "",
                "author_avatar_url": user.avatar_url.url if user.avatar_url else None,
                "content": serializer.validated_data["content"],
                "parent_id": parent_id,
                "create_time": now,
                "replies": [],
            }).data,
            status=status.HTTP_201_CREATED,
        )

    # ── POSTS BY USER ────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="by-user", permission_classes=[AllowAny])
    def by_user(self, request):
        author_id = request.query_params.get("author")
        if not author_id:
            return Response({"error": "author parameter required."}, status=status.HTTP_400_BAD_REQUEST)

        page_size = int(request.query_params.get("pageSize", 10))
        qs = PostsByUser.objects.filter(author_id=int(author_id))
        items, next_cursor = _paginate_cassandra(qs, page_size)

        # Fetch full post data
        posts_data = []
        for item in items:
            post = PostById.objects.filter(post_id=item.post_id).first()
            if post:
                posts_data.append(_post_to_dict(post))

        posts_data = _enrich_like_info(posts_data, request.user)
        return Response({
            "results": PostSerializer(posts_data, many=True).data,
            "nextCursor": next_cursor,
        })


# ── Health check endpoint ────────────────────────────────────────

class HealthViewSet(viewsets.ViewSet):
    """GET /api/health/ — dependency health check."""
    permission_classes = [AllowAny]

    def list(self, request):
        checks = {}

        # PostgreSQL
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks["postgresql"] = "ok"
        except Exception as e:
            checks["postgresql"] = str(e)

        # Cassandra
        try:
            from cassandra.cqlengine.connection import get_session
            get_session().execute("SELECT now() FROM system.local")
            checks["cassandra"] = "ok"
        except Exception as e:
            checks["cassandra"] = str(e)

        # Redis
        try:
            cache.set("_health", 1, timeout=5)
            cache.get("_health")
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = str(e)

        # Elasticsearch
        try:
            from core.elasticsearch_service import _get_client
            es = _get_client()
            if es and es.ping():
                checks["elasticsearch"] = "ok"
            else:
                checks["elasticsearch"] = "unavailable"
        except Exception as e:
            checks["elasticsearch"] = str(e)

        all_ok = all(v == "ok" for v in checks.values())
        return Response(
            {"status": "healthy" if all_ok else "degraded", "checks": checks},
            status=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


