"""Small authentication feature flags for server-rendered navigation."""
from django.conf import settings


def auth_features(request):
    return {
        "google_auth_enabled": bool(
            getattr(settings, "GOOGLE_CLIENT_ID", "")
            and getattr(settings, "GOOGLE_CLIENT_SECRET", "")
            and getattr(settings, "GOOGLE_REDIRECT_URI", "")
        ),
    }
