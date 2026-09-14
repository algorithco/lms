from django.apps import AppConfig


class WebapiConfig(AppConfig):
    """JSON API powering the React SPA (additive — existing HTML views untouched)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.webapi"
    verbose_name = "Web API (React)"
