# posts/serializers.py

from rest_framework import serializers
from .models import Post
from .models import Comment

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ['id','title', 'content', 'image_url', 'timestamp', 'geolocation', 'author', 'create_time', 'update_time']
        # It is required to let the overrided create() work
        read_only_fields = ['author'] # Mark 'author' as read-only to exclude it from user input
        

    def create(self, validated_data):
        author = self.context['author']
        return Post.objects.create(author=author, **validated_data)


class CommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()
    display_name = serializers.CharField(source='author.display_name', read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'post', 'author', 'content', 'parent', 'create_time', 'replies', 'display_name', 'avatar_url']

    def get_avatar_url(self, obj):
        if obj.author.avatar_url:
            return obj.author.avatar_url.url
        return None

    def get_replies(self, obj):
        # Serialize replies recursively
        if obj.replies.exists():
            return CommentSerializer(obj.replies.all(), many=True).data
        return []
    
class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['post', 'author', 'content', 'parent']
