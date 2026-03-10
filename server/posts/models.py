"""
PostgreSQL models for posts app.

Post/Comment/Like content lives in Cassandra (see cassandra_models.py).
This file is intentionally minimal — kept for Django migration history
so that the old Post/Comment tables can be dropped cleanly.
"""

from django.db import models