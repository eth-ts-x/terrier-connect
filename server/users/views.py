from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers as drf_serializers

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt import exceptions as simplejwt_exceptions
from rest_framework_simplejwt.tokens import RefreshToken

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView

from .models import UserFollowRel
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_auth_cookies(response, access_token, refresh_token=None):
    """Write access (and optionally refresh) JWT as HttpOnly cookies."""
    jwt_settings = settings.SIMPLE_JWT
    response.set_cookie(
        key=jwt_settings['AUTH_COOKIE'],
        value=access_token,
        max_age=int(jwt_settings['ACCESS_TOKEN_LIFETIME'].total_seconds()),
        secure=jwt_settings['AUTH_COOKIE_SECURE'],
        httponly=jwt_settings['AUTH_COOKIE_HTTP_ONLY'],
        samesite=jwt_settings['AUTH_COOKIE_SAMESITE'],
        path=jwt_settings['AUTH_COOKIE_PATH'],
        domain=jwt_settings['AUTH_COOKIE_DOMAIN'],
    )
    if refresh_token:
        response.set_cookie(
            key=jwt_settings['AUTH_COOKIE_REFRESH'],
            value=refresh_token,
            max_age=int(jwt_settings['REFRESH_TOKEN_LIFETIME'].total_seconds()),
            secure=jwt_settings['AUTH_COOKIE_SECURE'],
            httponly=jwt_settings['AUTH_COOKIE_HTTP_ONLY'],
            samesite=jwt_settings['AUTH_COOKIE_SAMESITE'],
            path=jwt_settings['AUTH_COOKIE_PATH'],
            domain=jwt_settings['AUTH_COOKIE_DOMAIN'],
        )


# ---------------------------------------------------------------------------
# Auth Views
# ---------------------------------------------------------------------------

class RegisterView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {'message': 'User registered successfully.', 'user': UserSerializer(user).data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CookieTokenObtainPairView(TokenObtainPairView):
    """
    POST /users/login/
    Authenticates with email + password.
    Returns tokens as HttpOnly cookies; response body contains only user data.
    """
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        if response.status_code == 200:
            access_token = response.data.pop('access', None)
            refresh_token = response.data.pop('refresh', None)
            _set_auth_cookies(response, access_token, refresh_token)
            try:
                user = User.objects.get(email=request.data.get('email'))
                response.data['user'] = UserSerializer(user).data
            except User.DoesNotExist:
                pass
        return super().finalize_response(request, response, *args, **kwargs)


class CookieTokenRefreshSerializer(TokenRefreshSerializer):
    """Fall back to reading the refresh token from the HttpOnly cookie."""
    refresh = drf_serializers.CharField(required=False)

    def validate(self, attrs):
        if not attrs.get('refresh'):
            cookie_name = settings.SIMPLE_JWT.get('AUTH_COOKIE_REFRESH', 'refresh_token')
            attrs['refresh'] = self.context['request'].COOKIES.get(cookie_name, '')
        if not attrs.get('refresh'):
            raise simplejwt_exceptions.InvalidToken('No valid refresh token found.')
        return super().validate(attrs)


class CookieTokenRefreshView(TokenRefreshView):
    """POST /users/token/refresh/ — issues a new access cookie from the refresh cookie."""
    serializer_class = CookieTokenRefreshSerializer
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        if response.status_code == 200:
            access_token = response.data.pop('access', None)
            _set_auth_cookies(response, access_token)
        return super().finalize_response(request, response, *args, **kwargs)


class LogoutView(APIView):
    """POST /users/logout/ — clears JWT cookies."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        response = Response({'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        jwt_settings = settings.SIMPLE_JWT
        response.delete_cookie(jwt_settings['AUTH_COOKIE'], path=jwt_settings['AUTH_COOKIE_PATH'])
        response.delete_cookie(jwt_settings['AUTH_COOKIE_REFRESH'], path=jwt_settings['AUTH_COOKIE_PATH'])
        return response


class MeView(APIView):
    """GET /users/me/ — returns the currently authenticated user's data."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


# ---------------------------------------------------------------------------
# User ViewSet
# ---------------------------------------------------------------------------

class UserViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET    /users/{id}/              - retrieve user profile (public)
    POST   /users/{id}/follow/       - follow a user
    DELETE /users/{id}/unfollow/     - unfollow a user
    GET    /users/{id}/followers/    - list followers (public)
    GET    /users/{id}/following/    - list following (public)
    PUT    /users/profile/           - update own profile
    PUT    /users/change-password/   - change password
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in ('retrieve', 'followers', 'following'):
            return [AllowAny()]
        return [IsAuthenticated()]

    # ------------------------------------------------------------------
    # Follow / Unfollow
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'])
    def follow(self, request, pk=None):
        target = self.get_object()
        if request.user == target:
            return Response({'error': 'Users cannot follow themselves.'}, status=status.HTTP_400_BAD_REQUEST)
        if UserFollowRel.objects.filter(follower=request.user, following=target).exists():
            return Response({'error': 'Already following this user.'}, status=status.HTTP_400_BAD_REQUEST)
        UserFollowRel.objects.create(follower=request.user, following=target)
        return Response(
            {'message': f'{request.user.display_name} is now following {target.display_name}.'},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['delete'])
    def unfollow(self, request, pk=None):
        target = self.get_object()
        try:
            rel = UserFollowRel.objects.get(follower=request.user, following=target)
        except UserFollowRel.DoesNotExist:
            return Response({'error': 'Not following this user.'}, status=status.HTTP_400_BAD_REQUEST)
        rel.delete()
        return Response(
            {'message': f'{request.user.display_name} has unfollowed {target.display_name}.'},
            status=status.HTTP_204_NO_CONTENT,
        )

    # ------------------------------------------------------------------
    # Followers / Following lists
    # ------------------------------------------------------------------

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def followers(self, request, pk=None):
        user = self.get_object()
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('pageSize', 10)
        rels = UserFollowRel.objects.filter(following=user).select_related('follower')
        paginator = Paginator(rels, page_size)
        try:
            paginated = paginator.page(page)
        except PageNotAnInteger:
            return Response({'error': 'Invalid page number.'}, status=status.HTTP_400_BAD_REQUEST)
        except EmptyPage:
            return Response({'error': 'Page out of range.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'page': page, 'pageSize': page_size,
            'totalItems': paginator.count, 'totalPages': paginator.num_pages,
            'results': [UserSerializer(rel.follower).data for rel in paginated],
        })

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def following(self, request, pk=None):
        user = self.get_object()
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('pageSize', 10)
        rels = UserFollowRel.objects.filter(follower=user).select_related('following')
        paginator = Paginator(rels, page_size)
        try:
            paginated = paginator.page(page)
        except PageNotAnInteger:
            return Response({'error': 'Invalid page number.'}, status=status.HTTP_400_BAD_REQUEST)
        except EmptyPage:
            return Response({'error': 'Page out of range.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'page': page, 'pageSize': page_size,
            'totalItems': paginator.count, 'totalPages': paginator.num_pages,
            'results': [UserSerializer(rel.following).data for rel in paginated],
        })

    # ------------------------------------------------------------------
    # Profile update / Change password
    # ------------------------------------------------------------------

    @action(detail=False, methods=['put', 'patch'], parser_classes=[MultiPartParser, FormParser])
    def profile(self, request):
        serializer = UserUpdateSerializer(
            request.user, data=request.data, partial=True, context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Profile updated successfully.',
                'user': UserSerializer(request.user).data,
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['put'], url_path='change-password')
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            request.user.set_password(serializer.validated_data['newPassword'])
            request.user.save()
            return Response({'message': 'Password updated successfully.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Google OAuth 2.0 Login
# ---------------------------------------------------------------------------

class GoogleLoginView(SocialLoginView):
    """
    POST /users/auth/google/
    Accepts { "access_token": "<google_access_token>" } or
            { "code": "<authorization_code>" }

    dj-rest-auth + allauth handle:
      1. Validate the token / exchange the code with Google
      2. Find-or-create the User (adapter links by email)
      3. Return JWT tokens as HttpOnly cookies
    """
    adapter_class = GoogleOAuth2Adapter
    callback_url = settings.GOOGLE_OAUTH_CALLBACK_URL
    client_class = OAuth2Client
    permission_classes = [AllowAny]

    def get_response(self):
        """Override to set JWT cookies instead of returning tokens in body."""
        response = super().get_response()
        user = self.user
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        _set_auth_cookies(response, access_token, refresh_token)
        # Strip tokens from body, add user data
        response.data.pop("access", None)
        response.data.pop("refresh", None)
        response.data.pop("access_token", None)
        response.data.pop("refresh_token", None)
        response.data["user"] = UserSerializer(user).data
        return response

