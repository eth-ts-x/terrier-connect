from rest_framework import serializers


class NotificationSerializer(serializers.Serializer):
    notification_id = serializers.UUIDField(read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    type = serializers.CharField(read_only=True)
    actor_id = serializers.IntegerField(read_only=True)
    actor_display_name = serializers.CharField(read_only=True)
    actor_avatar_url = serializers.CharField(read_only=True, allow_null=True)
    target_id = serializers.CharField(read_only=True)
    target_type = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    is_read = serializers.BooleanField(read_only=True)
    create_time = serializers.DateTimeField(read_only=True)
