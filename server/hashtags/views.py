"""
Hashtag API views.

Hashtag registry lives in PostgreSQL (autocomplete, trending).
Post-by-tag lookups go through Elasticsearch.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Hashtag
from .serializer import HashtagSerializer


class HashtagViewSet(viewsets.ModelViewSet):
    """
    list     GET  /hashtags/                      - auth required
    create   POST /hashtags/                      - auth required
    retrieve GET  /hashtags/{pk}/                 - auth required
    search   GET  /hashtags/search/?hashtag_text= - public
    bulk     POST /hashtags/bulk/                 - auth required
    posts    GET  /hashtags/{pk}/posts/            - public (ES)
    popular  GET  /hashtags/popular/              - public
    """
    queryset = Hashtag.objects.all()
    serializer_class = HashtagSerializer

    def get_permissions(self):
        if self.action in ("popular", "search", "posts"):
            return [AllowAny()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        hashtag_text = request.data.get("hashtag_text")
        if Hashtag.objects.filter(hashtag_text=hashtag_text).exists():
            return Response(
                {"error": "Hashtag already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def search(self, request):
        q = request.query_params.get("hashtag_text", "")
        hashtags = Hashtag.objects.filter(hashtag_text__icontains=q)[:20]
        return Response(HashtagSerializer(hashtags, many=True).data)

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        items = request.data
        created = []
        for item in items:
            text = item.get("hashtag_text")
            if text:
                _, was_created = Hashtag.objects.get_or_create(hashtag_text=text)
                if was_created:
                    created.append(text)
        all_tags = Hashtag.objects.filter(
            hashtag_text__in=[i.get("hashtag_text") for i in items]
        )
        return Response({
            "message": f"{len(created)} new hashtag(s) created.",
            "hashtags": HashtagSerializer(all_tags, many=True).data,
        })

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def posts(self, request, pk=None):
        """Return posts for a given hashtag via Elasticsearch."""
        from core.elasticsearch_service import search_by_hashtag

        try:
            hashtag = Hashtag.objects.get(pk=pk)
        except Hashtag.DoesNotExist:
            return Response({"error": "Hashtag not found."}, status=status.HTTP_404_NOT_FOUND)

        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("pageSize", 10))
        result = search_by_hashtag(hashtag.hashtag_text, page=page, page_size=page_size)
        return Response({
            "hashtag": hashtag.hashtag_text,
            "total": result["total"],
            "page": page,
            "pageSize": page_size,
            "results": result["results"],
        })

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def popular(self, request):
        """Return popular hashtags using Elasticsearch aggregation."""
        from core.elasticsearch_service import _get_client

        limit = int(request.query_params.get("limit", 10))
        es = _get_client()
        if not es:
            # Fallback: return latest hashtags from PG
            tags = Hashtag.objects.order_by("-created_time")[:limit]
            return Response(HashtagSerializer(tags, many=True).data)

        try:
            resp = es.search(
                index="posts",
                body={
                    "size": 0,
                    "aggs": {
                        "popular_tags": {
                            "terms": {
                                "field": "hashtags",
                                "size": limit,
                            }
                        }
                    },
                },
            )
            buckets = resp.get("aggregations", {}).get("popular_tags", {}).get("buckets", [])
            return Response([
                {"hashtag_text": b["key"], "count": b["doc_count"]}
                for b in buckets
            ])
        except Exception:
            tags = Hashtag.objects.order_by("-created_time")[:limit]
            return Response(HashtagSerializer(tags, many=True).data)

