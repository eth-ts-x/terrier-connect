from django.conf import settings
from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.db.models import Index


class Post(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    image_url = models.ImageField(upload_to='post_media/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    geolocation = models.CharField(max_length=255, blank=True, null=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    create_time = models.DateTimeField(auto_now_add=True)
    update_time = models.DateTimeField(auto_now=True)
    search_vector = SearchVectorField(null=True)

    def __str__(self):
        return f"Post {self.id} by {self.author.display_name}"

    class Meta:
        indexes = [
            Index(fields=['search_vector']),
        ]


class Comment(models.Model):
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    create_time = models.DateTimeField(auto_now_add=True)
    update_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Comment {self.id} by {self.author.display_name}"

    class Meta:
        indexes = [
            Index(fields=['post', 'parent']),
        ]
        ordering = ['create_time']