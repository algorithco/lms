"""
Settings additions for the project.
Add these to your project/settings.py
"""

# --- Channels ---
ASGI_APPLICATION = 'project.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',  # Dev only
        # Production: use Redis
        # 'BACKEND': 'channels_redis.core.RedisChannelLayer',
        # 'CONFIG': {
        #     "hosts": [('127.0.0.1', 6379)],
        #     "capacity": 1500,
        #     "expiry": 10,
        # },
    },
}

# --- LLM Settings ---
# LLM_MAX_WORKERS = 2  # Thread pool size for blocking LLM calls
# OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')  # Or your provider

# --- Database (SQLite optimization for dev) ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,  # Increase SQLite busy timeout
            # 'isolation_level': None,  # Autocommit mode (use with caution)
        },
    }
}

# For better SQLite concurrency in dev, consider:
# DATABASES['default']['OPTIONS']['init_command'] = 'PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;'

# --- CORS (if needed for frontend) ---
# CORS_ALLOWED_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']

# --- Logging ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'essays': {'level': 'DEBUG', 'handlers': ['console'], 'propagate': False},
        'quiz': {'level': 'DEBUG', 'handlers': ['console'], 'propagate': False},
        'channels': {'level': 'INFO', 'handlers': ['console'], 'propagate': False},
    },
}