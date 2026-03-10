import re

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Read-only serializer for public user data."""

    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'display_name', 'bio', 'avatar_url']

    def get_avatar_url(self, obj):
        if obj.avatar_url:
            return obj.avatar_url.url
        return None


class RegisterSerializer(serializers.Serializer):
    """Write-only serializer for user registration."""

    email = serializers.EmailField()
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(write_only=True, min_length=8)
    confirmPassword = serializers.CharField(write_only=True)
    avatar = serializers.ImageField(required=False)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email is already registered.')
        return value

    def validate_username(self, value):
        if User.objects.filter(display_name=value).exists():
            raise serializers.ValidationError('Username is already taken.')
        return value

    def validate(self, data):
        if data['password'] != data['confirmPassword']:
            raise serializers.ValidationError({'confirmPassword': 'Passwords do not match.'})
        password = data['password']
        if not (len(password) >= 8
                and re.search(r'\d', password)
                and re.search(r'[\W_]', password)):
            raise serializers.ValidationError({
                'password': (
                    'Password must be at least 8 characters long, '
                    'include a number, and a special character.'
                )
            })
        return data

    def create(self, validated_data):
        validated_data.pop('confirmPassword')
        username = validated_data.pop('username')
        avatar = validated_data.pop('avatar', None)
        password = validated_data.pop('password')
        email = validated_data['email']

        user = User(email=email, display_name=username)
        user.set_password(password)
        if avatar:
            user.avatar_url = avatar
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Partial-update serializer for user profile (supports multipart avatar upload)."""

    avatar_url = serializers.ImageField(required=False)

    class Meta:
        model = User
        fields = ['display_name', 'email', 'bio', 'avatar_url']
        extra_kwargs = {
            'display_name': {'required': False},
            'email': {'required': False},
            'bio': {'required': False},
        }

    def validate_email(self, value):
        if not value.endswith('@bu.edu'):
            raise serializers.ValidationError('Only @bu.edu email addresses are allowed.')
        request = self.context.get('request')
        if request and User.objects.exclude(id=request.user.id).filter(email=value).exists():
            raise serializers.ValidationError('Email already registered.')
        return value

    def validate_display_name(self, value):
        request = self.context.get('request')
        if request and User.objects.exclude(id=request.user.id).filter(display_name=value).exists():
            raise serializers.ValidationError('Display name already taken.')
        return value

    def update(self, instance, validated_data):
        new_avatar = validated_data.pop('avatar_url', None)
        if new_avatar:
            # Delete old avatar file if it exists
            if instance.avatar_url:
                try:
                    default_storage.delete(instance.avatar_url.name)
                except Exception:
                    pass
            avatar_path = default_storage.save(
                f'user_avatars/{instance.id}_{new_avatar.name}', new_avatar
            )
            instance.avatar_url = avatar_path
        return super().update(instance, validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for the change-password endpoint."""

    oldPassword = serializers.CharField(required=True)
    newPassword = serializers.CharField(required=True, min_length=8)
    confirmPassword = serializers.CharField(required=True)

    def validate_oldPassword(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate(self, data):
        if data['newPassword'] != data['confirmPassword']:
            raise serializers.ValidationError({'confirmPassword': 'New passwords do not match.'})
        password = data['newPassword']
        if not (len(password) >= 8
                and re.search(r'\d', password)
                and re.search(r'[\W_]', password)):
            raise serializers.ValidationError({
                'newPassword': (
                    'Password must be at least 8 characters long, '
                    'include a number, and a special character.'
                )
            })
        return data
