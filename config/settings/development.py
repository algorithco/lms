"""Development settings — SQLite, DEBUG=True, Celery eager mode."""
from .base import *  # noqa: F401,F403

DEBUG = True
DEV_PUBLIC_TUNNEL = env.bool("DEV_PUBLIC_TUNNEL", default=False)
DEV_EXTERNAL_HOSTS = env.list("DEV_EXTERNAL_HOSTS", default=[])
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"] + DEV_EXTERNAL_HOSTS
CSRF_TRUSTED_ORIGINS = env.list("DEV_CSRF_TRUSTED_ORIGINS", default=[])
if DEV_EXTERNAL_HOSTS and not DEV_PUBLIC_TUNNEL:
    raise ValueError("Set DEV_PUBLIC_TUNNEL=true for externally reachable development.")
if DEV_PUBLIC_TUNNEL and (
    not DEV_EXTERNAL_HOSTS
    or not CSRF_TRUSTED_ORIGINS
    or any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS)
):
    raise ValueError("Public development requires explicit hosts and HTTPS CSRF origins.")

# ---------------------------------------------------------------------------
# Cookie — ngrok orqali kirganda ishlashi uchun
# ---------------------------------------------------------------------------
SESSION_COOKIE_SECURE = DEV_PUBLIC_TUNNEL
CSRF_COOKIE_SECURE = DEV_PUBLIC_TUNNEL
SESSION_COOKIE_SAMESITE = "Lax" # ngrok proxysi orqali form postlari uchun
CSRF_COOKIE_SAMESITE = "Lax"   # ngrok proxysi orqali form postlari uchun
CSRF_COOKIE_HTTPONLY = False    # JS CSRF token o'qishi kerak

# ---------------------------------------------------------------------------
# Database — lightweight SQLite for local dev
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 60,  # Bazaga kirish uchun 60 soniyagacha kutishga ruxsat berish
            'transaction_mode': 'IMMEDIATE',
        },
    }
}

# ---------------------------------------------------------------------------
# Only a loopback-only development server may use permissive CORS. A public
# tunnel must name each browser origin explicitly.
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = not DEV_PUBLIC_TUNNEL
CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS if DEV_PUBLIC_TUNNEL else []

# ---------------------------------------------------------------------------
# Email — print to console
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# Celery — synchronous mode (no Redis required for testing)
# ---------------------------------------------------------------------------
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True  # Propagate exceptions in eager mode
