"""
Management command: python manage.py init_elasticsearch

Creates the Elasticsearch posts index with proper mappings.
Idempotent — safe to run on every container start.
"""

from django.core.management.base import BaseCommand
from core.elasticsearch_service import ensure_index


class Command(BaseCommand):
    help = "Create Elasticsearch index with mappings."

    def handle(self, *args, **options):
        self.stdout.write("Ensuring Elasticsearch index...")
        ensure_index()
        self.stdout.write(self.style.SUCCESS("Elasticsearch index ready."))
