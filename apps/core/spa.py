"""Serve the baked React SPA shell for legacy HTML routes.

After the React SPA cutover the page templates (payments/*, essays/*,
arena/*, ...) no longer exist — only emails/ + registration/*. Rendering
them raises TemplateDoesNotExist → HTTP 500 in production. The SPA Router
owns these paths now, so the Django page views answer with spa/index.html
(HTTP 200, no-cache); all data flows through the JSON APIs (JWT/session).

Pattern mirrors apps/telegram_app/views.py:tma_index_view.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


def serve_spa_shell(request: HttpRequest, fallback: str = "/") -> HttpResponse:
    """GET page → baked SPA shell (or SPA-route redirect when unbaked)."""
    spa_index = Path(settings.BASE_DIR) / "spa" / "index.html"
    try:
        html = spa_index.read_text(encoding="utf-8")
    except OSError:
        # No baked SPA (e.g. dev bind-mount hides /app/spa — the dev UI
        # runs on vite :5173 instead). Fall back to the SPA route.
        query = request.META.get("QUERY_STRING", "")
        return redirect(f"{fallback}?{query}" if query else fallback)
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    return response
