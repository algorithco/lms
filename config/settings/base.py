"""
Base Django settings — shared across all environments.

Environment-specific overrides live in development.py and production.py.
Uses django-environ for secure .env-based configuration.
"""
import environ
from pathlib import Path
from celery.schedules import crontab

# ---------------------------------------------------------------------------
# django-environ setup
# ---------------------------------------------------------------------------
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # lms_platform/

# Read .env file if it exists
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# ---------------------------------------------------------------------------
# Core Django
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me-in-production-!@#$%^&*()")
DEBUG = env("DEBUG", default=False)
ALLOWED_HOSTS = env("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    # Django built-ins (daphne must be before staticfiles)
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # JWT blacklist (logout)
    "drf_spectacular",       # OpenAPI / Swagger docs
    "corsheaders",           # CORS for API consumers
    "django_filters",        # queryset filtering in DRF
    "storages",              # S3 / cloud file storage

    # Local apps (models register here)
    "apps.accounts",
    "apps.courses",
    "apps.tests",            # "tests" is reserved in Python; app label below
    "apps.results",
    "apps.certificates",
    "apps.notifications",
    "apps.games",
    "apps.core",           # Maintenance tasks
    "apps.essays",         # Essay writing & AI grading
    "apps.telegram_app",   # Telegram Mini App
    "apps.arena",          # WebSocket Quiz Arena
    "apps.payments",       # Subscriptions & Payments
    "apps.panel",          # In-app admin panel (/control-panel/)
    "apps.webapi",         # JSON API for the React SPA (/api/v1/)
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Static files (gzip, brotli, cache headers)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.gzip.GZipMiddleware",  # Compress HTML/JSON responses
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.accounts.context_processors.auth_features",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database — defaults to SQLite; production overrides with PostgreSQL
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        **env.db(
            "DATABASE_URL",
            default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        ),
        # Persistent connections: reuse TCP connections to DB (saves ~5ms per query)
        "CONN_MAX_AGE": 600,
        # Connection timeout (seconds)
        "CONN_HEALTH_CHECKS": True,
    }
}

# ---------------------------------------------------------------------------
# Custom User Model  (must be set BEFORE first migration)
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_RESET_TIMEOUT = 60 * 60  # one-hour, single-use after password change

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
# Default UI language (UZ) — used when no session/cookie language is present.
# The platform's i18n system (apps.core.translations) falls back to "uz" too.
LANGUAGE_CODE = "uz"
LANGUAGES = [("uz", "O'zbek"), ("ru", "Русский"), ("en", "English")]
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & Media files.
# Project CSS/JS moved to the React SPA (frontend/dist, served by nginx from
# the spa_volume). static/ stays as an (empty) source dir so collectstatic
# keeps working; admin + DRF assets still come via AppDirectoriesFinder.
# templates/ keeps transactional email templates only (templates/emails/* +
# registration/password_reset_email*); all page templates are retired.
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# WhiteNoise: long-lived cache headers for static assets (1 year)
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]
WHITENOISE_MAX_AGE = 31536000  # 1 year for static assets
WHITENOISE_USE_FINDERS = True
WHITENOISE_MANIFEST_STRICT = False  # Don't crash if a file is missing
WHITENOISE_ALLOW_ALL_ORIGINS = False

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Site URL (for certificate verify links, etc.)
# ---------------------------------------------------------------------------
SITE_URL = env("SITE_URL", default="http://localhost:8000")

# ---------------------------------------------------------------------------
# Auth Redirects — SPA paths (server-rendered auth pages are retired).
# @login_required redirects land on the React login page; the SPA then uses
# the /api/auth/* JSON endpoints (see frontend/src/lib/api.ts).
# ---------------------------------------------------------------------------
LOGIN_URL = "/login"
LOGIN_REDIRECT_URL = "/dashboard"
LOGOUT_REDIRECT_URL = "/login"

# ---------------------------------------------------------------------------
# CORS (Cross-Origin Resource Sharing)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000"],
)

# ---------------------------------------------------------------------------
# Django REST Framework + Throttling
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    # Authentication
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],

    # Permissions
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],

    # Pagination
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,

    # Filtering
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],

    # Schema (drf-spectacular)
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",

    # Rate Limiting (Throttling)
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",      # Anonymous: 30 requests per minute
        "user": "100/minute",     # Authenticated: 100 requests per minute
        "test-start": "5/hour",   # Test start: 5 per hour
        "test-submit": "10/hour", # Test submit: 10 per hour
    },
}

# ---------------------------------------------------------------------------
# drf-spectacular (OpenAPI 3.0 / Swagger)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "LMS Platform API",
    "DESCRIPTION": (
        "Online Test & Learning Management System API.\n\n"
        "## Features\n"
        "- **Auth**: JWT-based registration, login, logout, profile management\n"
        "- **Tests**: Start attempts, auto-save answers, submit with timer\n"
        "- **Results**: View test results, analytics, statistics\n"
        "- **Certificates**: PDF certificate generation with QR verification\n"
        "- **Notifications**: Telegram bot integration\n\n"
        "## Authentication\n"
        "Use JWT Bearer token. Obtain via `/api/auth/login/` endpoint.\n"
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "CONTACT": {
        "name": "LMS Platform Support",
        "email": "support@lms-platform.uz",
    },
    "LICENSE": {
        "name": "MIT License",
    },

    # Tag grouping in Swagger UI
    "TAGS": [
        {"name": "Auth", "description": "Registration, login, logout, profile"},
        {"name": "Tests", "description": "Test listing and test-taking flow"},
        {"name": "Results", "description": "Test results and analytics"},
        {"name": "Certificates", "description": "PDF certificate generation and verification"},
        {"name": "Notifications", "description": "Telegram bot notifications"},
    ],

    # JWT Bearer security scheme
    "COMPONENT_SPLIT_REQUEST": True,
    "COMPONENT_NO_READ_ONLY_REQUIRED": True,
    "ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE": False,

    # Sorters
    "SORTERS": ["drf_spectacular.generators.OpenApiSchemaGenerator"],

    # Authentication classes for Swagger UI
    "AUTHENTICATION_WHITELIST": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],

    # Search
    "SCHEMA_PATH_PREFIX": r"/api/",
}

# ---------------------------------------------------------------------------
# JWT (SimpleJWT)
# ---------------------------------------------------------------------------
from datetime import timedelta

SIMPLE_JWT = {
    # Token lifetime
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,

    # Signature algorithm
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,

    # Auth header
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",

    # Token claim field name
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",

    # Custom token claims
    "TOKEN_OBTAIN_SERIALIZER": "apps.accounts.serializers.CustomTokenObtainPairSerializer",
}

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 120       # 2 minutes max per task
CELERY_TASK_SOFT_TIME_LIMIT = 90   # 1.5 min soft limit
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Bound the Celery/Redis connection pools so heavy web traffic can never
# exhaust Redis connections and starve the Telegram bot's own connections.
CELERY_BROKER_POOL_LIMIT = env("CELERY_BROKER_POOL_LIMIT", default=10)
CELERY_REDIS_MAX_CONNECTIONS = env("CELERY_REDIS_MAX_CONNECTIONS", default=20)

# Synchronous mode for testing (no Redis needed)
CELERY_TASK_ALWAYS_EAGER = env("CELERY_TASK_ALWAYS_EAGER", default=False)

# Celery Beat schedule (periodic tasks)
CELERY_BEAT_SCHEDULE = {
    # Check for timed-out test attempts every 60 seconds
    "check-timeout-attempts": {
        "task": "core.check_timeout_attempts",
        "schedule": 60.0,
    },
    # Cleanup stale attempts every 15 minutes
    "cleanup-stale-attempts": {
        "task": "core.cleanup_stale_attempts",
        "schedule": 60.0 * 15,  # 15 minutes
    },
    # Cleanup expired sessions every 6 hours
    "cleanup-sessions": {
        "task": "core.cleanup_expired_sessions",
        "schedule": 60.0 * 60 * 6,  # 6 hours
    },
    # Full maintenance at 3 AM daily
    "daily-maintenance": {
        "task": "core.daily_maintenance",
        "schedule": crontab(hour=3, minute=0),
    },
    # Auto-submit expired essays every 2 minutes
    "auto-submit-expired-essays": {
        "task": "essays.auto_submit_expired",
        "schedule": 120.0,  # 2 minutes
    },
}

# ---------------------------------------------------------------------------
# ASGI & Django Channels (WebSocket)
# ---------------------------------------------------------------------------
ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",  # Dev: in-memory; Prod: Redis
        # "BACKEND": "channels_redis.core.RedisChannelLayer",
        # "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
    },
}

# Anti-fraud certificate secret
CERTIFICATE_SECRET_KEY = env(
    "CERTIFICATE_SECRET_KEY",
    default=SECRET_KEY[:32],
)

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

# ---------------------------------------------------------------------------
# Telegram Bot
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
# Bot username (without @) — used for deep links, CTAs and auth widgets.
TELEGRAM_BOT_NAME = env("TELEGRAM_BOT_NAME", default="uz_essaygrader_bot")
TELEGRAM_API_URL = "https://api.telegram.org"

# ---------------------------------------------------------------------------
# Manual payments (card transfer + Telegram receipt verification)
# ---------------------------------------------------------------------------
PAYMENT_CARD_NUMBER = env("PAYMENT_CARD_NUMBER", default="4073 4200 3846 0386")
PAYMENT_CARD_BANK = env("PAYMENT_CARD_BANK", default="Uzum Bank")
PAYMENT_CARD_HOLDER = env("PAYMENT_CARD_HOLDER", default="Lobar Mansurova")
PAYMENT_ADMIN_USERNAME = env("PAYMENT_ADMIN_USERNAME", default="rozievkomiljon")

# Secret token for webhook mode. When set, the /telegram/webhook/ endpoint
# rejects requests without the X-Telegram-Bot-Api-Secret-Token header.
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET", default="")
TELEGRAM_WEBHOOK_MODE = env.bool("TELEGRAM_WEBHOOK_MODE", default=False)

# ---------------------------------------------------------------------------
# Web Push (VAPID)
# ---------------------------------------------------------------------------
VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY", default="")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY", default="")
VAPID_CLAIM_EMAIL = env("VAPID_CLAIM_EMAIL", default="mailto:admin@lms-platform.uz")

# ---------------------------------------------------------------------------
# Essay Grading
# ---------------------------------------------------------------------------
ESSAY_TARGET_SCALE = env("ESSAY_TARGET_SCALE", default=75, cast=int)
ESSAY_OFF_TOPIC_SCORE = env("ESSAY_OFF_TOPIC_SCORE", default=35, cast=int)

# Essay AI Provider (OpenAI-compatible APIs)
#   "auto"      (default) — use whichever provider has a configured API key
#   "openrouter"           — force OpenRouter (requires OPENROUTER_API_KEY)
#   "groq"                 — force Groq (requires GROQ_API_KEY)
#
# IMPORTANT: keys are never shared across providers. Sending a Groq key
# (gsk_...) to OpenRouter's endpoint returns a misleading
# 401 "Missing Authentication header" — that confusion is prevented here.
ESSAY_AI_PROVIDER = env("ESSAY_AI_PROVIDER", default="auto")

# API keys — each provider reads its own env var only.
# Generic aliases AI_API_KEY / AI_BASE_URL / AI_MODEL are also accepted for
# simple .env setups; the explicit OPENROUTER_* / ESSAY_AI_MODEL names win.
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", default=env("AI_API_KEY", default=""))
GROQ_API_KEY = env("GROQ_API_KEY", default="")

# Model selection. Set ESSAY_AI_MODEL to force a model on either provider;
# otherwise each provider falls back to its own default below.
#
# Model zanjiri (OpenRouter, DTM/BMB Milliy sertifikat esselari):
#   1) nvidia/nemotron-3.5-lightning:free  — asosiy (eng tez)
#   2) liquid/lfm-2.5-2.6b:free            — fallback 1
#   3) nvidia/nemotron-3-super-120b-a12b:free — fallback 2
# Eski "nvidia/nemotron-3-super:free" (va ":free"siz varianti) OpenRouter
# katalogida YO'Q — 400 "is not a valid model ID" berardi. Katalogdagi to'g'ri
# nemotron-3-super ID'si: nvidia/nemotron-3-super-120b-a12b:free
# (2026-09 tekshirildi: ai_smoke_test --validate-models).
# Bu bepul modellar ba'zan fikrlash matni yozadi / JSON'ni yarmida kesadi —
# buni services.py tomonda hal qilamiz: qat'iy JSON rejimi
# (response_format=json_object), ixcham prompt (1-2 jumla reason),
# max_tokens=3000, temperature=0.1 va parse_llm_json'ning mustahkam
# extraction/tuzatish mantiqi. Zanjir bo'ylab fallback + soddalashtirilgan
# prompt bilan retry bepul modellarni barqaror qiladi.
ESSAY_AI_MODEL = env("ESSAY_AI_MODEL", default=env("AI_MODEL", default=""))
OPENROUTER_AI_MODEL = env("OPENROUTER_AI_MODEL", default="nvidia/nemotron-3.5-lightning:free")
GROQ_AI_MODEL = env("GROQ_AI_MODEL", default="llama-3.3-70b-versatile")

# Fallback chain: tried in order when the primary model hits a rate limit /
# server error / model-unavailable (404) / empty reply. Comma-separated.
# The legacy single OPENROUTER_FALLBACK_MODEL var (if set) is appended for
# backward compatibility. Empty string disables all fallbacks.
_OPENROUTER_FALLBACK_DEFAULT = (
    "liquid/lfm-2.5-2.6b:free,"
    "nvidia/nemotron-3-super-120b-a12b:free"
)
OPENROUTER_FALLBACK_MODELS = [
    m.strip()
    for m in env("OPENROUTER_FALLBACK_MODELS", default=_OPENROUTER_FALLBACK_DEFAULT).split(",")
    if m.strip()
]
_legacy_single_fallback = env("OPENROUTER_FALLBACK_MODEL", default="").strip()
if _legacy_single_fallback and _legacy_single_fallback not in OPENROUTER_FALLBACK_MODELS:
    OPENROUTER_FALLBACK_MODELS.append(_legacy_single_fallback)
GROQ_FALLBACK_MODEL = env("GROQ_FALLBACK_MODEL", default="")

# Provider endpoints (OpenAI-compatible)
OPENROUTER_BASE_URL = env(
    "OPENROUTER_BASE_URL", default=env("AI_BASE_URL", default="https://openrouter.ai/api/v1")
)
GROQ_BASE_URL = env("GROQ_BASE_URL", default="https://api.groq.com/openai/v1")

# OpenRouter specific settings (referrer headers)
OPENROUTER_SITE_URL = env("OPENROUTER_SITE_URL", default="http://localhost:8000")
OPENROUTER_APP_NAME = env("OPENROUTER_APP_NAME", default="LMS Platform")

# Mock mode for development (only used when ESSAY_AI_MOCK_MODE=True AND no API key)
ESSAY_AI_MOCK_MODE = env.bool("ESSAY_AI_MOCK_MODE", default=False)

# LLM so'rovi uchun READ timeout (sekund). Connect timeout alohida 10s.
# Ixcham prompt + qat'iy JSON rejimi bilan 60s yetarli; OpenRouter sekinlashsa
# _chat_with_fallback model-zanjiri bo'ylab retry qiladi. Task limitlari
# (soft 200s / hard 240s) bu qiymatdan katta bo'lishi shart.
ESSAY_AI_REQUEST_TIMEOUT = float(env("ESSAY_AI_REQUEST_TIMEOUT", default="60"))

# Background-thread retry backoff (sekund) — runserver-only rejimda
# (CELERY_TASK_ALWAYS_EAGER=True) grading shu thread'da 3 urinish qiladi.
# Prod default 5,10,15s; local tezlik uchun .env'da 1,2,3 ga tushiring.
# Development settings buni avtomatik tezlashtiradi.
def _parse_thread_backoff(raw: str) -> tuple:
    try:
        parts = [float(p.strip()) for p in str(raw).split(",") if p.strip()]
        parts = [p for p in parts if p > 0]
        if len(parts) >= 3:
            return (parts[0], parts[1], parts[2])
        if parts:
            while len(parts) < 3:
                parts.append(parts[-1])
            return (parts[0], parts[1], parts[2])
    except (TypeError, ValueError):
        pass
    return (5.0, 10.0, 15.0)


ESSAY_THREAD_RETRY_BACKOFF = _parse_thread_backoff(
    env("ESSAY_THREAD_RETRY_BACKOFF", default="5,10,15")
)

# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")
GOOGLE_REDIRECT_URI = env(
    "GOOGLE_REDIRECT_URI",
    default=f"{SITE_URL}/api/auth/google/callback/",
)

# ---------------------------------------------------------------------------
# Security (Production)
# ---------------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_COOKIE_HTTPONLY = False  # Must be False so JS can read CSRF token for ngrok/proxy setups
SESSION_COOKIE_HTTPONLY = True

# These should be enabled in production
# SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", default=False)
# SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS", default=0)
# SECURE_HSTS_INCLUDE_SUBDOMAINS = env("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
# SECURE_HSTS_PRELOAD = env("SECURE_HSTS_PRELOAD", default=False)
# SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", default=False)
# CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", default=False)
