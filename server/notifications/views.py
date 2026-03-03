"""
Notification API views.

Notifications are stored in Cassandra (NotificationsByUser).
Written by Kafka consumers; read + marked-as-read by this API.
"""

import logging
from datetime import datetime

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .cassandra_models import NotificationsByUser
from .serializers import NotificationSerializer

logger = logging.getLogger("terrierconnect.notifications")


class NotificationViewSet(viewsets.ViewSet):
    """
    list        GET    /notifications/            - list user's notifications
    mark_read   POST   /notifications/mark-read/  - mark all as read
    unread_count GET   /notifications/unread-count/ - count unread
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        page_size = int(request.query_params.get("pageSize", 20))
        notifications = list(
            NotificationsByUser.objects.filter(user_id=request.user.id).limit(page_size)
        )
        data = []
        for n in notifications:
            data.append({
                "notification_id": n.notification_id,
                "user_id": n.user_id,
                "type": n.type,
                "actor_id": n.actor_id,
                "actor_display_name": n.actor_display_name or "",
                "actor_avatar_url": n.actor_avatar_url,
                "target_id": n.target_id,
                "target_type": n.target_type,
                "message": n.message or "",
                "is_read": n.is_read,
                "create_time": n.create_time,
            })
        return Response({
            "results": NotificationSerializer(data, many=True).data,
        })

    @action(detail=False, methods=["post"], url_path="mark-read")
    def mark_read(self, request):
        """Mark all unread notifications as read for the current user."""
        # Fetch recent notifications then filter is_read in Python
        # (is_read is not in the primary key, so Cassandra can't filter it).
        recent = list(
            NotificationsByUser.objects.filter(user_id=request.user.id).limit(200)
        )
        unread = [n for n in recent if not n.is_read]
        for n in unread:
            NotificationsByUser.objects(
                user_id=n.user_id,
                create_time=n.create_time,
                notification_id=n.notification_id,
            ).update(is_read=True)
        return Response({"marked": len(unread)})

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """Return count of unread notifications."""
        # Fetch recent notifications and count unread in Python
        # (is_read is not in the primary key, so Cassandra can't filter it).
        recent = list(
            NotificationsByUser.objects.filter(user_id=request.user.id).limit(100)
        )
        count = sum(1 for n in recent if not n.is_read)
        return Response({"count": count})
