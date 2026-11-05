"""Fast, isolated test settings. Never use for a reachable development server."""

from .development import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
    # Only the explicitly throttled scopes; cache is cleared per test where it matters.
    "DEFAULT_THROTTLE_RATES": {"feedback-submit": "5/hour", "question-issue": "30/hour", "essay-ocr": "20/hour", "essay-submit": "5/minute", "essay-autosave": "60/minute", "speaking-submit": "10/hour", "ai-tools": "30/hour"},
}
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
