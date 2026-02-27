from rest_framework import serializers
from .models import Post, Comment


class PostSerializer(serializers.ModelSerializer):
    author_display_name = serializers.CharField(source='author.display_name', read_only=True)
    author_avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'content', 'image_url', 'timestamp', 'geolocation',
            'author', 'author_display_name', 'author_avatar_url',
            'create_time', 'update_time',
        ]
        read_only_fields = ['author', 'author_display_name', 'author_avatar_url']

    def get_author_avatar_url(self, obj):
        if obj.author.avatar_url:
            return obj.author.avatar_url.url
        return None

    def create(self, validated_data):
        # author is injected via perform_create(serializer.save(author=...))
        return Post.objects.create(**validated_data)


class CommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()
    display_name = serializers.CharField(source='author.display_name', read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'post', 'author', 'content', 'parent', 'create_time', 'replies', 'display_name', 'avatar_url']
        read_only_fields = ['author']

    def get_avatar_url(self, obj):
        if obj.author.avatar_url:
            return obj.author.avatar_url.url
        return None

    def get_replies(self, obj):
        if obj.replies.exists():
            return CommentSerializer(obj.replies.all(), many=True).data
        return []


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['post', 'author', 'content', 'parent']
        read_only_fields = ['author']
