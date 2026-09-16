"""Production settings — PostgreSQL, security hardening."""
import os

from .base import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", SECRET_KEY)
# Strip whitespace (users often write "a.com, www.a.com") and always allow
# internal healthcheck hosts (curl 127.0.0.1:8000 + nginx->web) so Docker
# HEALTHCHECK never 400s even if operator forgets them in .env.prod.
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if h.strip()
]
for _internal in ("127.0.0.1", "localhost", "web"):
    if _internal not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_internal)

# HTTPS is terminated at Nginx — tell Django it is behind a proxy so
# request.is_secure() and SECURE_SSL_REDIRECT behave correctly.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Domains allowed to send POSTs with a CSRF cookie (https://example.com,
# https://www.example.com). Without this, every form POST behind HTTPS 403s.
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

# ---------------------------------------------------------------------------
# Database — PostgreSQL (production)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "lms_platform"),
        "USER": os.environ.get("DB_USER", "lms_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "db"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "OPTIONS": {
            "connect_timeout": 10,
        },
        # Reuse DB connections (daphne is long-lived) + probe before reuse
        # so Postgres restarts/idle closes don't cause 500s.
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
    }
}

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
# Explicit SameSite (defense in depth; Django 5.2 default is Lax already)
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# Nginx already redirects HTTP → HTTPS (port 80), so Django-level redirect
# would break internal healthchecks (curl to 127.0.0.1:8000) and is redundant.
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ---------------------------------------------------------------------------
# Upload limits — cap request bodies (JSON APIs, form POSTs) and in-memory
# file uploads so a single request can't exhaust worker memory. Files larger
# than FILE_UPLOAD_MAX_MEMORY_SIZE spill to disk; view-level checks below
# additionally cap CSV imports at 5 MB.
# ---------------------------------------------------------------------------
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB request body
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024    # 5 MB before spill-to-disk

# ---------------------------------------------------------------------------
# Channels — Redis channel layer (WebSockets across workers/processes)
# The Arena broadcasts quiz state via group_send, so production MUST use
# Redis (in-memory only works inside a single process).
# capacity bounds the per-process connection pool so a WebSocket burst can
# never exhaust Redis connections and starve the bot / Celery clients.
# ---------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("REDIS_URL", "redis://redis:6379/1")],
            "capacity": 100,           # max connections per process pool
            "expiry": 60,              # channel message TTL (seconds)
            "group_expiry": 3600,      # stale groups reaped after 1h
        },
    },
}

# ---------------------------------------------------------------------------
# Cache — unified Redis cache (DB 2)
# Without this Django silently uses per-process LocMemCache, which breaks
# DRF throttling and shared caching across multiple daphne workers. The pool
# is bounded via max_connections so the cache can't starve the bot's Redis.
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("CACHE_REDIS_URL", "redis://redis:6379/2"),
        "TIMEOUT": 300,
        "OPTIONS": {
            "max_connections": 100,
            "health_check_interval": 30,
        },
        "KEY_PREFIX": "lms",
    }
}

# ---------------------------------------------------------------------------
# Email — SMTP
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")

# ---------------------------------------------------------------------------
# Telegram Bot Token (from environment)
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# ---------------------------------------------------------------------------
# CORS — restrict to known origins (empty entries stripped)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

# ---------------------------------------------------------------------------
# Logging — structured console output for `docker compose logs`
# ---------------------------------------------------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.request": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "django.db.backends": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "celery": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "daphne": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Sentry — optional (set SENTRY_DSN to enable). No-op when empty so the
# sentry-sdk dependency in requirements/production.txt is not dead code.
# ---------------------------------------------------------------------------
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,
        )
    except Exception:  # never break boot on observability errors
        pass

# ---------------------------------------------------------------------------
# Startup safety net — fail loudly instead of running insecure
# ---------------------------------------------------------------------------
from django.core.exceptions import ImproperlyConfigured  # noqa: E402

_TEMPLATE_KEYS = {
    "django-insecure-change-me-in-production-!@#$%^&*()",
    "your-super-secret-key-change-this-in-production",
}
_PLACEHOLDER_FRAGMENTS = ("change-me", "changeme", "change_this", "change-this", "your-")
if (
    not SECRET_KEY
    or SECRET_KEY in _TEMPLATE_KEYS
    or len(SECRET_KEY) < 32
    or any(frag in SECRET_KEY.lower() for frag in _PLACEHOLDER_FRAGMENTS)
):
    raise ImproperlyConfigured(
        "SECRET_KEY must be a long random value via the DJANGO_SECRET_KEY env var "
        "in production (no placeholders, min 32 chars). Generate one with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )
if not ALLOWED_HOSTS or all(h in ("127.0.0.1", "localhost", "web") for h in ALLOWED_HOSTS):
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must be set explicitly in production "
        "(comma-separated), e.g. example.com,www.example.com."
    )
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured(
        "DJANGO_CSRF_TRUSTED_ORIGINS must be set in production "
        "(comma-separated), e.g. https://example.com,https://www.example.com."
    )
# A PostgreSQL password is mandatory — the compose file already fails fast via
# the DB_PASSWORD:? interpolation, this guards non-compose deploys too.
if not os.environ.get("DB_PASSWORD"):
    raise ImproperlyConfigured(
        "DB_PASSWORD must be set in production (PostgreSQL password)."
    )
if not CERTIFICATE_SECRET_KEY or len(CERTIFICATE_SECRET_KEY) < 16:
    raise ImproperlyConfigured(
        "CERTIFICATE_SECRET_KEY must be set to a random value in production "
        "(independent from DJANGO_SECRET_KEY)."
    )
if os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").lower() in ("1", "true", "yes"):
    raise ImproperlyConfigured(
        "CELERY_TASK_ALWAYS_EAGER must not be true in production (would run LLM inline)."
    )
if os.environ.get("ESSAY_AI_MOCK_MODE", "").lower() in ("1", "true", "yes"):
    raise ImproperlyConfigured(
        "ESSAY_AI_MOCK_MODE must not be true in production."
    )
