"""
Celery application configuration.

Uses Redis as the broker for task queue management.
Handles async tasks: PDF generation, Telegram notifications, etc.
"""
import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
# Respects the deployed environment: production compose sets
# DJANGO_SETTINGS_MODULE=config.settings.production, so setdefault never
# overrides it. The development fallback keeps local `celery -A config worker`
# simple without extra env setup.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("lms_platform")

# Read config from Django settings; the CELERY namespace means
# all celery-related configuration keys must be prefixed with `CELERY_`.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:
    """Debug task for testing Celery connectivity."""
    print(f"Request: {self.request!r}")
