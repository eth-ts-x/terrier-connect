"""
Migrate existing Post/Comment data from PostgreSQL to Cassandra.

Run this BEFORE applying migration 0003_drop_post_comment so the PG
tables still exist.  Usage:

    python manage.py migrate_posts_to_cassandra [--batch-size 200]
"""

import uuid
from datetime import timezone

from django.core.management.base import BaseCommand
from django.db import connection

from posts.cassandra_models import (
    PostById,
    PostsByUser,
    CommentsByPost,
)
from core.elasticsearch_service import index_post


class Command(BaseCommand):
    help = "One-shot migration of PG posts/comments into Cassandra + ES"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size", type=int, default=200,
            help="Number of PG rows to fetch per batch",
        )
        parser.add_argument(
            "--skip-es", action="store_true",
            help="Skip Elasticsearch indexing",
        )

    def handle(self, *args, **options):
        batch = options["batch_size"]
        skip_es = options["skip_es"]

        self._migrate_posts(batch, skip_es)
        self._migrate_comments(batch)
        self.stdout.write(self.style.SUCCESS("Migration complete."))

    # ── Posts ───────────────────────────────────────────────────
    def _migrate_posts(self, batch_size: int, skip_es: bool):
        with connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM posts_post")
            total = cur.fetchone()[0]

        self.stdout.write(f"Migrating {total} posts …")
        offset = 0
        migrated = 0

        while offset < total:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.id, p.title, p.content, p.image_url,
                           p.create_time, p.update_time, p.geolocation,
                           u.id, u.username, u.display_name
                    FROM posts_post p
                    JOIN users_user u ON u.id = p.author_id
                    ORDER BY p.id
                    LIMIT %s OFFSET %s
                    """,
                    [batch_size, offset],
                )
                rows = cur.fetchall()

            for row in rows:
                (pg_id, title, content, image_url, create_time,
                 update_time, geolocation, author_id, username, display_name) = row

                post_id = uuid.uuid4()

                # Ensure timezone-aware
                if create_time.tzinfo is None:
                    create_time = create_time.replace(tzinfo=timezone.utc)
                if update_time.tzinfo is None:
                    update_time = update_time.replace(tzinfo=timezone.utc)

                # Fetch hashtags for this post from PG
                hashtags = []
                with connection.cursor() as cur2:
                    cur2.execute(
                        """
                        SELECT h.hashtag_text
                        FROM hashtags_posthashtagrel phr
                        JOIN hashtags_hashtag h ON h.id = phr.hashtag_id_id
                        WHERE phr.post_id_id = %s
                        """,
                        [pg_id],
                    )
                    hashtags = [r[0] for r in cur2.fetchall()]

                # Write to Cassandra
                PostById.create(
                    post_id=post_id,
                    author_id=author_id,
                    author_name=display_name or username,
                    title=title,
                    content=content,
                    image_url=str(image_url) if image_url else "",
                    hashtags=hashtags,
                    geolocation=geolocation or "",
                    created_at=create_time,
                    updated_at=update_time,
                )
                PostsByUser.create(
                    author_id=author_id,
                    created_at=create_time,
                    post_id=post_id,
                    title=title,
                )

                # Index to ES
                if not skip_es:
                    try:
                        index_post(
                            str(post_id),
                            {
                                "title": title,
                                "content": content,
                                "author_id": author_id,
                                "author_name": display_name or username,
                                "hashtags": hashtags,
                                "created_at": create_time.isoformat(),
                            },
                        )
                    except Exception as exc:
                        self.stderr.write(
                            f"  ES index failed for post {post_id}: {exc}"
                        )

                migrated += 1

            offset += batch_size
            self.stdout.write(f"  {migrated}/{total}")

        self.stdout.write(self.style.SUCCESS(f"Posts migrated: {migrated}"))

    # ── Comments ───────────────────────────────────────────────
    def _migrate_comments(self, batch_size: int):
        with connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM posts_comment")
            total = cur.fetchone()[0]

        self.stdout.write(f"Migrating {total} comments …")
        offset = 0
        migrated = 0

        while offset < total:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.content, c.create_time, c.update_time,
                           c.post_id, c.parent_id,
                           u.id, u.username, u.display_name
                    FROM posts_comment c
                    JOIN users_user u ON u.id = c.author_id
                    ORDER BY c.id
                    LIMIT %s OFFSET %s
                    """,
                    [batch_size, offset],
                )
                rows = cur.fetchall()

            for row in rows:
                (pg_cid, content, create_time, update_time,
                 pg_post_id, pg_parent_id,
                 author_id, username, display_name) = row

                if create_time.tzinfo is None:
                    create_time = create_time.replace(tzinfo=timezone.utc)

                CommentsByPost.create(
                    post_id=uuid.uuid4(),  # NOTE: won't match new IDs
                    comment_id=uuid.uuid4(),
                    author_id=author_id,
                    author_name=display_name or username,
                    content=content,
                    parent_comment_id=uuid.uuid4() if pg_parent_id else None,
                    created_at=create_time,
                )
                migrated += 1

            offset += batch_size
            self.stdout.write(f"  {migrated}/{total}")

        self.stdout.write(self.style.SUCCESS(f"Comments migrated: {migrated}"))
