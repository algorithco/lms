"""
Custom middleware for development/proxy environments.

Fixes CSRF issues when accessing Django through ngrok, cloudflare tunnels,
or other reverse proxies where the Origin header changes on restart.
"""
import logging
import re

from django.conf import settings
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)

# Ngrok URL patterns (free tier and paid)
NGROK_ORIGINS_RE = re.compile(
    r"^https://[a-z0-9-]+\.ngrok(?:-free)?\.(?:app|dev)$"
)


class NgrokCsrfMiddleware:
    """
    In development, dynamically trusts ngrok origins for CSRF.

    Without this, every ngrok URL restart would require manually updating
    CSRF_TRUSTED_ORIGINS — which users forget to do, causing 403 CSRF errors
    on every POST request (login, register, form submissions).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only in DEBUG mode — production should have explicit origins
        if settings.DEBUG:
            origin = request.META.get("HTTP_ORIGIN") or request.META.get(
                "HTTP_REFERER", ""
            )
            if origin and NGROK_ORIGINS_RE.match(origin):
                # Dynamically add to trusted origins if not already there
                if origin not in settings.CSRF_TRUSTED_ORIGINS:
                    settings.CSRF_TRUSTED_ORIGINS.append(origin)
                    logger.info("Auto-trusted ngrok origin: %s", origin)

        return self.get_response(request)
