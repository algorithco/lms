"""
Django config package.

Import celery app so that tasks are discovered when Django starts.
This ensures @shared_task decorators are registered at import time.
"""
from .celery import app as celery_app

__all__ = ("celery_app",)
