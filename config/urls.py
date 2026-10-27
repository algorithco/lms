"""Root URL configuration for LMS Platform."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.core.spa import serve_spa_shell
from apps.core.views_seo import robots_txt_view, sitemap_xml_view
from apps.web.views import set_language_view

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),
    # API schema & docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    # Health check (container orchestration)
    path("healthz/", include("apps.core.urls")),
    # App APIs (JSON) — MUST come before SPA fallback
    path("api/auth/", include("apps.accounts.urls")),
    path("api/courses/", include("apps.courses.urls")),
    path("api/tests/", include("apps.tests.urls")),
    path("api/results/", include("apps.results.urls")),
    path("api/certificates/", include("apps.certificates.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.webapi.urls")),  # React SPA API
    # Legacy app HTML routes — serve React SPA shell
    # These apps have been updated to use serve_spa_shell()
    path("essays/", include("apps.essays.urls")),
    path("arena/", include("apps.arena.urls")),
    path("tma/", include("apps.telegram_app.urls")),
    path("subscribe/", include("apps.payments.urls")),
    # Games included in apps.web.urls with namespace="games"
    # Web app routes (auth, dashboard, home, password-reset, certificate-verify, games)
    # Kept for test compatibility and legacy URL namespace.
    # These serve the SPA shell via serve_spa_shell().
    path("", include("apps.web.urls")),
    # Language switching (used by tests and server-side rendering)
    path("set-language/<str:lang>/", set_language_view, name="set-language"),
    # In-app admin panel (staff / role='admin' only) — serves SPA shell
    path("control-panel/", include("apps.panel.urls")),
    # SEO sitemap & robots
    path("sitemap.xml", sitemap_xml_view, name="sitemap-xml"),
    path("robots.txt", robots_txt_view, name="robots-txt"),
    # SPA fallback — catches all remaining routes and serves React SPA shell
    # This must be LAST so it doesn't intercept API/admin/static/media paths
    path("", serve_spa_shell, name="spa-shell"),
    path("<path:resource>", serve_spa_shell, name="spa-shell-deep"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
