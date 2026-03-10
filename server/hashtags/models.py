from django.db import models


class Hashtag(models.Model):
    """Simple registry for hashtag autocomplete and trending.

    Posts store hashtags denormalized in Cassandra.
    Post-by-tag lookups go through Elasticsearch.
    """
    hashtag_text = models.CharField(max_length=100, unique=True)
    created_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.hashtag_text
