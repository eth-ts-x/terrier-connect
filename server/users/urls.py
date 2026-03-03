from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    RegisterView,
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    LogoutView,
    MeView,
    UserViewSet,
    GoogleLoginView,
)

router = DefaultRouter()
router.register(r'', UserViewSet, basename='user')

urlpatterns = [
    # Auth endpoints
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CookieTokenObtainPairView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('me/', MeView.as_view(), name='me'),
    # Google OAuth 2.0
    path('auth/google/', GoogleLoginView.as_view(), name='google_login'),
    # ViewSet routes (retrieve, follow, unfollow, followers, following, profile, change-password)
    path('', include(router.urls)),
]
