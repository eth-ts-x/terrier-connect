from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Custom manager that uses email instead of username."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model using email as the primary identifier.
    Inherits password hashing, is_active, is_staff, is_superuser
    and the full Django auth pipeline from AbstractUser.
    """
    username = None  # Remove the default username field
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=100, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    avatar_url = models.ImageField(upload_to='user_avatars/', blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # email + password are enough for createsuperuser

    objects = UserManager()

    def __str__(self):
        return self.email


class UserFollowRel(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.follower.display_name} follows {self.following.display_name}"
