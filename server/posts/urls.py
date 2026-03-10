from django.urls import path, include
from rest_framework.routers import SimpleRouter

from .views import PostViewSet, HealthViewSet

router = SimpleRouter()
router.register(r"", PostViewSet, basename="post")

urlpatterns = [
    path("health/", HealthViewSet.as_view({"get": "list"}), name="posts-health"),
    path("", include(router.urls)),
]
