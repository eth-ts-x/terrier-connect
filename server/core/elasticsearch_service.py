"""
Thin read-only wrapper around the Elasticsearch Python client.
Used by Django views for the search API.
"""

import logging
from typing import Any

from django.conf import settings
from elasticsearch import Elasticsearch

logger = logging.getLogger("terrierconnect.elasticsearch")

_client: Elasticsearch | None = None


def _get_client() -> Elasticsearch | None:
    global _client
    if _client is not None:
        return _client
    try:
        _client = Elasticsearch(settings.ELASTICSEARCH_URL)
        info = _client.info()
        logger.info("Elasticsearch connected: %s", info.get("version", {}).get("number"))
    except Exception:
        logger.warning("Elasticsearch unavailable", exc_info=True)
    return _client


def search_posts(query: str, page: int = 1, page_size: int = 10) -> dict[str, Any]:
    """
    Full-text search across post title and content.
    Returns {"total": int, "results": [{"post_id": ..., "highlight": ...}]}
    """
    client = _get_client()
    if client is None:
        return {"total": 0, "results": []}

    body = {
        "from": (page - 1) * page_size,
        "size": page_size,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["title^2", "content", "hashtags"],
                "fuzziness": "AUTO",
            }
        },
        "highlight": {
            "fields": {"title": {}, "content": {"fragment_size": 200}},
        },
        "sort": [{"_score": "desc"}, {"create_time": "desc"}],
    }

    resp = client.search(index=settings.ELASTICSEARCH_INDEX_POSTS, body=body)
    hits = resp["hits"]
    results = []
    for hit in hits["hits"]:
        src = hit["_source"]
        src["_score"] = hit["_score"]
        src["highlight"] = hit.get("highlight", {})
        results.append(src)

    return {
        "total": hits["total"]["value"],
        "results": results,
    }


def search_by_hashtag(tag: str, page: int = 1, page_size: int = 10) -> dict[str, Any]:
    """Filter posts by exact hashtag match."""
    client = _get_client()
    if client is None:
        return {"total": 0, "results": []}

    body = {
        "from": (page - 1) * page_size,
        "size": page_size,
        "query": {"term": {"hashtags": tag}},
        "sort": [{"create_time": "desc"}],
    }

    resp = client.search(index=settings.ELASTICSEARCH_INDEX_POSTS, body=body)
    hits = resp["hits"]
    results = [hit["_source"] for hit in hits["hits"]]

    return {"total": hits["total"]["value"], "results": results}


def index_post(post_data: dict) -> None:
    """Index or update a single post document."""
    client = _get_client()
    if client is None:
        return
    client.index(
        index=settings.ELASTICSEARCH_INDEX_POSTS,
        id=str(post_data["post_id"]),
        document=post_data,
    )


def delete_post(post_id: str) -> None:
    """Remove a post document."""
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(index=settings.ELASTICSEARCH_INDEX_POSTS, id=post_id)
    except Exception:
        logger.warning("ES delete failed for post_id=%s", post_id, exc_info=True)


def ensure_index():
    """Create the posts index with proper mappings if it doesn't exist."""
    client = _get_client()
    if client is None:
        return
    index = settings.ELASTICSEARCH_INDEX_POSTS
    try:
        if client.indices.exists(index=index):
            return
    except Exception:
        logger.warning("ES indices.exists check failed, attempting create", exc_info=True)
    try:
        client.indices.create(
            index=index,
            mappings={
                "properties": {
                    "post_id": {"type": "keyword"},
                    "title": {"type": "text", "analyzer": "standard"},
                    "content": {"type": "text", "analyzer": "standard"},
                    "hashtags": {"type": "keyword"},
                    "author_id": {"type": "integer"},
                    "author_display_name": {"type": "text"},
                    "author_avatar_url": {"type": "keyword", "index": False},
                    "image_url": {"type": "keyword", "index": False},
                    "geolocation": {"type": "keyword"},
                    "create_time": {"type": "date"},
                    "update_time": {"type": "date"},
                }
            },
            settings={
                "number_of_shards": 1,
                "number_of_replicas": 0,
            },
        )
        logger.info("Elasticsearch index '%s' created", index)
    except Exception:
        logger.error("Failed to create Elasticsearch index '%s'", index, exc_info=True)
