import json

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models.signals import post_save
from django.dispatch import receiver

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Post, Comment
from .serializers import PostSerializer, CommentSerializer, CommentCreateSerializer
from hashtags.models import PostHashtagRel, Hashtag
from hashtags.views import add_post_hashtags_rel
from users.models import UserFollowRel


# ---------------------------------------------------------------------------
# Post ViewSet
# ---------------------------------------------------------------------------

class PostViewSet(viewsets.ModelViewSet):
    """
    list     GET  /posts/                - public (supports ?flag=following for auth)
    create   POST /posts/                - auth required
    retrieve GET  /posts/{id}/           - public
    update   PUT  /posts/{id}/           - auth, author only
    destroy  DELETE /posts/{id}/         - auth, author only
    search   GET  /posts/search/         - public  (?query=)
    by_tag   GET  /posts/by-tag/         - public  (?tag=)
    comment_list  GET  /posts/{id}/comments/ - public
    add_comment   POST /posts/{id}/comments/add/ - auth required
    """
    serializer_class = PostSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Post.objects.all().order_by('-create_time')

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'search', 'by_tag', 'comment_list'):
            return [AllowAny()]
        return [IsAuthenticated()]

    # ------------------------------------------------------------------
    # list
    # ------------------------------------------------------------------

    def list(self, request):
        flag = request.query_params.get('flag', 'all')
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('pageSize', 10)

        if flag == 'following':
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {'error': 'Authentication required for following feed.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            followed_ids = UserFollowRel.objects.filter(
                follower=request.user
            ).values_list('following_id', flat=True)
            posts = Post.objects.filter(author_id__in=followed_ids).order_by('-create_time')
        else:
            posts = Post.objects.all().order_by('-create_time')

        paginator = Paginator(posts, page_size)
        try:
            paginated_posts = paginator.page(page)
        except PageNotAnInteger:
            return Response({'error': 'Invalid page number.'}, status=status.HTTP_400_BAD_REQUEST)
        except EmptyPage:
            return Response({'error': 'Page out of range.'}, status=status.HTTP_404_NOT_FOUND)

        posts_data = []
        for post in paginated_posts:
            data = PostSerializer(post).data
            data['hashtags'] = list(
                PostHashtagRel.objects.filter(post_id=post)
                .values_list('hashtag_id__hashtag_text', flat=True)
            )
            posts_data.append(data)

        return Response({
            'page': page, 'pageSize': page_size,
            'totalItems': paginator.count, 'totalPages': paginator.num_pages,
            'results': posts_data,
        })

    # ------------------------------------------------------------------
    # retrieve
    # ------------------------------------------------------------------

    def retrieve(self, request, pk=None):
        try:
            post = Post.objects.get(pk=pk)
        except Post.DoesNotExist:
            return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)
        data = PostSerializer(post).data
        data['hashtags'] = list(
            PostHashtagRel.objects.filter(post_id=post)
            .values_list('hashtag_id__hashtag_text', flat=True)
        )
        return Response(data)

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def create(self, request, *args, **kwargs):
        hashtags_raw = request.data.get('hashtags', '[]')
        try:
            hashtags = json.loads(hashtags_raw)
        except (json.JSONDecodeError, TypeError):
            hashtags = []
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            add_post_hashtags_rel(serializer.instance, hashtags)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # update
    # ------------------------------------------------------------------

    def update(self, request, pk=None, **kwargs):
        try:
            post = Post.objects.get(pk=pk, author=request.user)
        except Post.DoesNotExist:
            return Response({'error': 'Post not found or not authorized.'}, status=status.HTTP_404_NOT_FOUND)
        hashtags_raw = request.data.get('hashtags', '[]')
        try:
            hashtags = json.loads(hashtags_raw)
        except (json.JSONDecodeError, TypeError):
            hashtags = []
        serializer = PostSerializer(post, data=request.data, partial=kwargs.get('partial', False))
        if serializer.is_valid():
            serializer.save()
            PostHashtagRel.objects.filter(post_id=post).delete()
            add_post_hashtags_rel(serializer.instance, hashtags)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # destroy
    # ------------------------------------------------------------------

    def destroy(self, request, pk=None):
        try:
            post = Post.objects.get(pk=pk, author=request.user)
        except Post.DoesNotExist:
            return Response({'error': 'Post not found or not authorized.'}, status=status.HTTP_404_NOT_FOUND)
        post.delete()
        return Response({'message': 'Post deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)

    # ------------------------------------------------------------------
    # Extra actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def search(self, request):
        query = request.query_params.get('query', '')
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('pageSize', 10)
        if not query:
            return Response({'error': 'No query parameter provided.'}, status=status.HTTP_400_BAD_REQUEST)
        search_query = SearchQuery(query)
        search_vector = SearchVector('content')
        posts = Post.objects.annotate(
            rank=SearchRank(search_vector, search_query)
        ).filter(search_vector=search_query).order_by('-rank', '-create_time')
        paginator = Paginator(posts, page_size)
        try:
            paginated = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            return Response({'error': 'Page out of range.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'page': page, 'pageSize': page_size,
            'totalItems': paginator.count, 'totalPages': paginator.num_pages,
            'results': PostSerializer(paginated, many=True).data,
        })

    @action(detail=False, methods=['get'], url_path='by-tag', permission_classes=[AllowAny])
    def by_tag(self, request):
        tag = request.query_params.get('tag')
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('pageSize', 10)
        if not tag:
            return Response({'error': 'tag parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            hashtag = Hashtag.objects.get(hashtag_text=tag)
        except Hashtag.DoesNotExist:
            return Response({'error': f'Hashtag "{tag}" not found.'}, status=status.HTTP_404_NOT_FOUND)
        posts = [rel.post_id for rel in PostHashtagRel.objects.filter(hashtag_id=hashtag)]
        paginator = Paginator(posts, page_size)
        try:
            paginated = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            return Response({'error': 'Page out of range.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'page': page, 'pageSize': page_size,
            'totalItems': paginator.count, 'totalPages': paginator.num_pages,
            'results': PostSerializer(paginated, many=True).data,
        })

    @action(detail=True, methods=['get'], url_path='comments', permission_classes=[AllowAny])
    def comment_list(self, request, pk=None):
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('pageSize', 10)
        comments = Comment.objects.filter(
            post_id=pk, parent__isnull=True
        ).select_related('author').prefetch_related('replies').order_by('create_time')
        paginator = Paginator(comments, page_size)
        try:
            paginated = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            return Response({'error': 'Page out of range.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'page': page, 'pageSize': page_size,
            'totalItems': paginator.count, 'totalPages': paginator.num_pages,
            'results': CommentSerializer(paginated, many=True).data,
        })

    @action(detail=True, methods=['post'], url_path='comments/add')
    def add_comment(self, request, pk=None):
        data = request.data.copy()
        data['post'] = pk
        serializer = CommentCreateSerializer(data=data)
        if serializer.is_valid():
            serializer.save(author=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Comment ViewSet
# ---------------------------------------------------------------------------

class CommentViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    create  POST /posts/comments/          - auth required
    update  PUT  /posts/comments/{id}/     - auth, author only
    destroy DELETE /posts/comments/{id}/   - auth, author only
    by_author GET /posts/comments/by-author/?author={id} - public
    """
    serializer_class = CommentCreateSerializer

    def get_queryset(self):
        return Comment.objects.all()

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def update(self, request, pk=None, **kwargs):
        try:
            comment = Comment.objects.get(pk=pk, author=request.user)
        except Comment.DoesNotExist:
            return Response({'error': 'Comment not found or not authorized.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommentCreateSerializer(comment, data=request.data, partial=kwargs.get('partial', False))
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        try:
            comment = Comment.objects.get(pk=pk, author=request.user)
        except Comment.DoesNotExist:
            return Response({'error': 'Comment not found or not authorized.'}, status=status.HTTP_404_NOT_FOUND)
        comment.delete()
        return Response({'message': 'Comment deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='by-author', permission_classes=[AllowAny])
    def by_author(self, request):
        author_id = request.query_params.get('author')
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('pageSize', 10)
        if not author_id:
            return Response({'error': 'author query param is required.'}, status=status.HTTP_400_BAD_REQUEST)
        comments = Comment.objects.filter(author_id=author_id).order_by('-create_time')
        paginator = Paginator(comments, page_size)
        try:
            paginated = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            return Response({'error': 'Page out of range.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'page': page, 'pageSize': page_size,
            'totalItems': paginator.count, 'totalPages': paginator.num_pages,
            'results': CommentSerializer(paginated, many=True).data,
        })


# ---------------------------------------------------------------------------
# Search-vector signal (keep existing behaviour)
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Post)
def update_search_vector(sender, instance, **kwargs):
    if not hasattr(instance, '_updating_search_vector'):
        instance._updating_search_vector = True
        instance.search_vector = SearchVector('content')
        instance.save()
        del instance._updating_search_vector

