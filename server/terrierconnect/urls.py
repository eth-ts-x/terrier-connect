"""
URL configuration for Terrier Connect.
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("api/admin/", admin.site.urls),
    path("api/posts/", include("posts.urls")),
    path("api/hashtags/", include("hashtags.urls")),
    path("api/users/", include("users.urls")),
    path("api/notifications/", include("notifications.urls")),
    # Prometheus metrics
    path("", include("django_prometheus.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
