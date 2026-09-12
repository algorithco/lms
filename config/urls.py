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

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # API schema & docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # Web pages (HTML)
    path("", include("apps.web.urls")),

    # Health check (container orchestration)
    path("healthz/", include("apps.core.urls")),

    # App APIs
    path("api/auth/", include("apps.accounts.urls")),
    path("api/courses/", include("apps.courses.urls")),
    path("api/tests/", include("apps.tests.urls")),
    path("api/results/", include("apps.results.urls")),
    path("api/certificates/", include("apps.certificates.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    # Games API: removed — duplicate of web/games/. Use web-games namespace via web/urls.py
    path("essays/", include("apps.essays.urls")),
    path("arena/", include("apps.arena.urls")),

    # In-app admin panel (staff / role='admin' only)
    path("control-panel/", include("apps.panel.urls")),
    path("tma/", include("apps.telegram_app.urls")),
    path("subscribe/", include("apps.payments.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
