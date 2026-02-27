from datetime import datetime, timedelta

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Hashtag, PostHashtagRel
from .serializer import HashtagSerializer
from posts.serializers import PostSerializer


class HashtagViewSet(viewsets.ModelViewSet):
    """
    list     GET  /hashtags/                      - auth required
    create   POST /hashtags/                      - auth required
    retrieve GET  /hashtags/{pk}/                 - auth required
    update   PUT  /hashtags/{pk}/                 - auth required
    destroy  DELETE /hashtags/{pk}/               - auth required
    search   GET  /hashtags/search/?hashtag_text= - auth required
    bulk     POST /hashtags/bulk/                 - auth required
    add_relations POST /hashtags/add-relations/   - auth required
    by_post  GET  /hashtags/by-post/{post_id}/    - auth required
    posts    GET  /hashtags/{pk}/posts/            - auth required
    popular  GET  /hashtags/popular/              - public
    """
    queryset = Hashtag.objects.all()
    serializer_class = HashtagSerializer

    def get_permissions(self):
        if self.action == 'popular':
            return [AllowAny()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        hashtag_text = request.data.get('hashtag_text')
        if Hashtag.objects.filter(hashtag_text=hashtag_text).exists():
            return Response(
                {'error': 'Hashtag with this text already exists.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def search(self, request):
        q = request.query_params.get('hashtag_text', '')
        hashtags = Hashtag.objects.filter(hashtag_text__icontains=q)
        return Response(HashtagSerializer(hashtags, many=True).data)

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        items = request.data
        new_hashtags = []
        for item in items:
            text = item.get('hashtag_text')
            if text and not Hashtag.objects.filter(hashtag_text=text).exists():
                new_hashtags.append(Hashtag(hashtag_text=text))
        existing = Hashtag.objects.filter(
            hashtag_text__in=[i.get('hashtag_text') for i in items]
        )
        if new_hashtags:
            Hashtag.objects.bulk_create(new_hashtags)
            return Response(
                {'message': 'Hashtags created.', 'hashtags': HashtagSerializer(existing, many=True).data},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {'message': 'No new hashtags to add.', 'hashtags': HashtagSerializer(existing, many=True).data},
        )

    @action(detail=False, methods=['post'], url_path='add-relations')
    def add_relations(self, request):
        post_id = request.data.get('post_id')
        hashtag_ids = request.data.get('hashtag_ids', [])
        if not post_id or not hashtag_ids:
            return Response(
                {'error': 'post_id and hashtag_ids are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rels = []
        for hid in hashtag_ids:
            if not Hashtag.objects.filter(id=hid).exists():
                return Response(
                    {'error': f'Hashtag {hid} does not exist.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            rels.append(PostHashtagRel(post_id_id=post_id, hashtag_id_id=hid))
        PostHashtagRel.objects.bulk_create(rels)
        return Response({'message': 'Relations created.'}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path=r'by-post/(?P<post_id>[^/.]+)')
    def by_post(self, request, post_id=None):
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('pageSize', 10)
        rels = PostHashtagRel.objects.filter(post_id=post_id)
        hashtags = [rel.hashtag_id for rel in rels]
        paginator = Paginator(hashtags, page_size)
        try:
            paginated = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            return Response({'error': 'Page out of range.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'page': page, 'pageSize': page_size,
            'totalItems': paginator.count, 'totalPages': paginator.num_pages,
            'results': HashtagSerializer(paginated, many=True).data,
        })

    @action(detail=True, methods=['get'])
    def posts(self, request, pk=None):
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('pageSize', 10)
        order_by = request.query_params.get('orderBy', '-post_id__create_time')
        rels = PostHashtagRel.objects.filter(hashtag_id=pk).order_by(order_by)
        post_objs = [rel.post_id for rel in rels]
        paginator = Paginator(post_objs, page_size)
        try:
            paginated = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            return Response({'error': 'Page out of range.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'page': page, 'pageSize': page_size,
            'totalItems': paginator.count, 'totalPages': paginator.num_pages,
            'results': PostSerializer(paginated, many=True).data,
        })

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def popular(self, request):
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('pageSize', 10)
        last_24h = datetime.now() - timedelta(hours=24)
        rels = PostHashtagRel.objects.filter(created_time__gte=last_24h).select_related('hashtag_id')
        count_map = {}
        text_map = {}
        for rel in rels:
            hid = rel.hashtag_id_id
            count_map[hid] = count_map.get(hid, 0) + 1
            text_map.setdefault(hid, rel.hashtag_id.hashtag_text)
        top = sorted(count_map.items(), key=lambda x: x[1], reverse=True)[:10]
        result = [{'id': k, 'hashtag_text': text_map[k], 'count': v} for k, v in top]
        paginator = Paginator(result, page_size)
        try:
            paginated = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            return Response({'error': 'Page out of range.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'page': page, 'pageSize': page_size,
            'totalItems': paginator.count, 'totalPages': paginator.num_pages,
            'results': list(paginated),
        })


# ---------------------------------------------------------------------------
# Standalone helper — imported by posts/views.py
# ---------------------------------------------------------------------------

def add_post_hashtags_rel(post, hashtags):
    """Create PostHashtagRel rows for a post; create missing Hashtag rows as needed."""
    if not hashtags:
        return
    instances = []
    for text in hashtags:
        hashtag, _ = Hashtag.objects.get_or_create(hashtag_text=text)
        instances.append(hashtag)
    PostHashtagRel.objects.bulk_create(
        [PostHashtagRel(post_id=post, hashtag_id=h) for h in instances]
    )
