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
    In development, allow ngrok origins for CSRF without mutating global settings.

    The previous implementation appended to settings.CSRF_TRUSTED_ORIGINS per
    request (thread-unsafe, unbounded growth, and matched against Referer paths
    that never equal an origin). This version is stateless: it validates the
    request Origin/Referer against the ngrok pattern per-request and sets a
    request-local flag. CSRF_TRUSTED_ORIGINS must still be configured
    explicitly (DEV_CSRF_TRUSTED_ORIGINS); this middleware only documents the
    intent and never mutates global state.

    NOTE: not in MIDDLEWARE (verified) — kept for explicit opt-in dev use only.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only in DEBUG mode — production should have explicit origins.
        # Stateless: no global mutation; expose per-request allowance for
        # logging/debugging. Actual CSRF trust comes from settings.
        if settings.DEBUG:
            origin = request.META.get("HTTP_ORIGIN") or request.META.get(
                "HTTP_REFERER", ""
            )
            if origin:
                # Compare origin host only (Referer includes a path).
                from urllib.parse import urlsplit

                try:
                    parts = urlsplit(origin)
                    candidate = f"{parts.scheme}://{parts.netloc}" if parts.netloc else ""
                except Exception:
                    candidate = ""
                if candidate and NGROK_ORIGINS_RE.match(candidate):
                    request.META["LMS_NGROK_ORIGIN_ALLOWED"] = candidate
                    logger.info("Ngrok origin seen (not auto-trusted): %s", candidate)

        return self.get_response(request)
