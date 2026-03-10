"""
Rebuild the Elasticsearch posts index from Cassandra data.

Drops and recreates the index, then bulk-indexes every PostById row.

    python manage.py rebuild_search_index [--batch-size 500]
"""

from django.core.management.base import BaseCommand

from posts.cassandra_models import PostById
from core.elasticsearch_service import ensure_index, index_post, _get_client


class Command(BaseCommand):
    help = "Rebuild the Elasticsearch posts index from Cassandra"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size", type=int, default=500,
            help="Bulk-index batch size",
        )
        parser.add_argument(
            "--drop", action="store_true",
            help="Drop the existing index before rebuilding",
        )

    def handle(self, *args, **options):
        es = _get_client()
        if es is None:
            self.stderr.write("Elasticsearch unavailable — aborting.")
            return

        if options["drop"]:
            self.stdout.write("Dropping existing index …")
            try:
                es.indices.delete(index="posts", ignore_unavailable=True)
            except Exception as exc:
                self.stderr.write(f"  Could not drop index: {exc}")

        self.stdout.write("Ensuring index mapping …")
        ensure_index()

        self.stdout.write("Scanning Cassandra PostById table …")
        count = 0
        batch = []

        for post in PostById.objects.all():
            doc = {
                "title": post.title,
                "content": post.content,
                "author_id": post.author_id,
                "author_name": post.author_name,
                "hashtags": list(post.hashtags) if post.hashtags else [],
                "created_at": post.created_at.isoformat()
                if post.created_at else None,
            }
            batch.append({"_index": "posts", "_id": str(post.post_id), "_source": doc})
            count += 1

            if len(batch) >= options["batch_size"]:
                self._flush(batch)
                batch = []
                self.stdout.write(f"  indexed {count} …")

        if batch:
            self._flush(batch)

        self.stdout.write(self.style.SUCCESS(f"Done — {count} posts indexed."))

    @staticmethod
    def _flush(actions):
        from elasticsearch.helpers import bulk
        bulk(_get_client(), actions, raise_on_error=False)
