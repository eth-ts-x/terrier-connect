"""
Management command: python manage.py init_cassandra

Creates the Cassandra keyspace and syncs all table schemas.
Idempotent — safe to run on every container start.
"""

from django.core.management.base import BaseCommand
from core.cassandra_connection import ensure_schema


class Command(BaseCommand):
    help = "Create Cassandra keyspace and sync table schemas."

    def handle(self, *args, **options):
        self.stdout.write("Syncing Cassandra schema...")
        ensure_schema()
        self.stdout.write(self.style.SUCCESS("Cassandra schema ready."))
