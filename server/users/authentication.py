from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django.conf import settings


class JWTCookieAuthentication(JWTAuthentication):
    """
    Extends simplejwt's JWTAuthentication to read the access token from an
    HttpOnly cookie (settings.SIMPLE_JWT['AUTH_COOKIE']) instead of the
    Authorization header.  Falls back to the header if the cookie is absent,
    so endpoints that need to support both (e.g. mobile clients) still work.
    """

    def authenticate(self, request):
        cookie_name = settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token")
        raw_token = request.COOKIES.get(cookie_name)

        if raw_token is None:
            # Fall back to standard Bearer-token header behaviour
            return super().authenticate(request)

        try:
            validated_token = self.get_validated_token(raw_token)
        except InvalidToken:
            return None

        return self.get_user(validated_token), validated_token
