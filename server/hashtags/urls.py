from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import HashtagViewSet

router = DefaultRouter()
router.register(r'', HashtagViewSet, basename='hashtag')

urlpatterns = [
    path('', include(router.urls)),
]
