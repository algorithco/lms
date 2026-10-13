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


def serve_spa_shell(request: HttpRequest, fallback: str = "/", resource: str = "") -> HttpResponse:
    """GET page → baked SPA shell (or SPA-route redirect when unbaked)."""
    spa_index = Path(settings.BASE_DIR) / "spa" / "index.html"
    frontend_dist_index = Path(settings.BASE_DIR) / "frontend" / "dist" / "index.html"

    for candidate in (spa_index, frontend_dist_index):
        try:
            html = candidate.read_text(encoding="utf-8")
            response = HttpResponse(html, content_type="text/html; charset=utf-8")
            response["Cache-Control"] = "no-cache"
            return response
        except OSError:
            continue

    # No baked SPA on disk.
    query = request.META.get("QUERY_STRING", "")
    target = f"{fallback}?{query}" if query else fallback

    # Guard against redirect loop: if redirect target matches request.path, never redirect to self.
    current_path = request.path
    if target == current_path or fallback == current_path or target.rstrip("/") == current_path.rstrip("/"):
        if getattr(settings, "DEBUG", False):
            vite_url = f"http://localhost:5173{current_path}"
            if query:
                vite_url = f"{vite_url}?{query}"
            return HttpResponse(
                f"""<!DOCTYPE html>
<html>
<head><title>SPA Shell (Dev Mode)</title></head>
<body style="font-family:system-ui,sans-serif;padding:2rem;text-align:center;line-height:1.5;">
  <h2>Grandec LMS — Frontend Unbaked</h2>
  <p>The baked SPA shell (<code>spa/index.html</code> or <code>frontend/dist/index.html</code>) was not found on disk.</p>
  <p>If running the Vite dev server, navigate to: <a href="{vite_url}">{vite_url}</a></p>
  <p>Or build the frontend assets: <code>cd frontend &amp;&amp; npm run build</code></p>
</body>
</html>""",
                content_type="text/html; charset=utf-8",
                status=200,
            )
        return HttpResponse(
            "Service Unavailable: SPA shell not built.",
            status=503,
            content_type="text/plain; charset=utf-8",
        )

    return redirect(target)
