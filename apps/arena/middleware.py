"""
apps/arena/middleware.py
JWT Authentication middleware for Django Channels WebSockets.
"""
from __future__ import annotations

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_str: str):
    """Decode SimpleJWT access token and return the active User instance or AnonymousUser."""
    try:
        token = AccessToken(token_str)
        user_id = token["user_id"]
        return User.objects.filter(id=user_id, is_active=True).first() or AnonymousUser()
    except (InvalidToken, TokenError, Exception) as exc:
        logger.debug("WebSocket JWT auth failed: %s", exc)
        return AnonymousUser()


class JwtAuthMiddleware:
    """
    Channels middleware that extracts a SimpleJWT access token from:
    1. Query string: ?token=<jwt>
    2. Header: Authorization: Bearer <jwt>

    If a valid token is provided, populates `scope["user"]` with the active user.
    If scope["user"] is already authenticated (e.g. from session) and no JWT is given,
    preserves it. Otherwise sets AnonymousUser().
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        user = scope.get("user")

        token: str | None = None

        # 1. Try query string: ?token=...
        query_string = scope.get("query_string", b"").decode("utf-8")
        if query_string:
            qs = parse_qs(query_string)
            if "token" in qs and qs["token"]:
                token = qs["token"][0]

        # 2. Try Authorization header: Bearer <token>
        if not token:
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode("utf-8")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1].strip()

        if token:
            resolved_user = await get_user_from_token(token)
            if resolved_user and resolved_user.is_authenticated:
                scope["user"] = resolved_user
            else:
                scope["user"] = AnonymousUser()
        elif not user:
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)


def JwtAuthMiddlewareStack(inner):
    """Stack that combines AuthMiddlewareStack with JwtAuthMiddleware."""
    from channels.auth import AuthMiddlewareStack
    return AuthMiddlewareStack(JwtAuthMiddleware(inner))
