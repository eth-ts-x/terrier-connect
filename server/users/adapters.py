"""
Custom allauth adapter.

Links social accounts to existing users with the same email,
rather than creating a duplicate account.
"""

from allauth.account.utils import user_field
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AutoLinkSocialAccountAdapter(DefaultSocialAccountAdapter):
    """If a user with the same email already exists, link the social
    login to that existing account instead of raising an error."""

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            return

        email = sociallogin.account.extra_data.get("email")
        if not email:
            return

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return

        sociallogin.connect(request, user)

    def populate_user(self, request, sociallogin, data):
        """Pre-fill user fields from Google profile data."""
        user = super().populate_user(request, sociallogin, data)
        user_field(user, "display_name", data.get("name", ""))
        return user
