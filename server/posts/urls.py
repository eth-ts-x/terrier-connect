from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PostViewSet, HealthViewSet

router = DefaultRouter()
router.register(r"", PostViewSet, basename="post")

health_router = DefaultRouter()
health_router.register(r"health", HealthViewSet, basename="health")

urlpatterns = [
    path("", include(health_router.urls)),
    path("", include(router.urls)),
]
