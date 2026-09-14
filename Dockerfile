# ============================================================================
# LMS Platform — Production Dockerfile (multi-stage)
#
# The app is ASGI (Django Channels / WebSockets for the Arena), so it runs
# under daphne, not gunicorn. weasyprint (PDF certificates) needs pango/cairo
# system libraries, installed in the final stage.
# ============================================================================

# ----------------------------------------------------------------------------
# Stage 1: builder — install Python deps into a wheelhouse
# ----------------------------------------------------------------------------
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /wheels

# Build deps (psycopg2-binary ships wheels, but keep for any sdist fallback)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ /wheels/requirements/
RUN pip wheel --wheel-dir /wheels/dist -r /wheels/requirements/production.txt

# ----------------------------------------------------------------------------
# Stage 1b: frontend-builder — build the React SPA.
# The dist/ output is copied into the runtime image at /app/spa and published
# to nginx via the spa_volume (see entrypoint + compose). VITE_API_URL is
# unset on purpose: the SPA uses same-origin relative URLs (nginx serves the
# SPA and proxies /api/* to Django), so no CORS is needed.
# ----------------------------------------------------------------------------
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ----------------------------------------------------------------------------
# Stage 2: runtime
# ----------------------------------------------------------------------------
FROM python:3.13-slim

# DJANGO_SETTINGS_MODULE is deliberately NOT set here: dev compose uses
# config.settings.development, prod compose uses .env.prod (production).
# Settings are injected per-environment via env_file / environment.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PORT=8000

# Runtime system libraries:
#   - libpq5: psycopg2 runtime
#   - pango/cairo/gdk-pixbuf/shared-mime-info: weasyprint (PDF certificates)
#   - curl: healthcheck
#   - tzdata: correct timestamps
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        curl \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN groupadd -r app && useradd -r -g app -d /app app

WORKDIR /app

# Install wheels from the builder stage
COPY --from=builder /wheels/dist /wheels/dist
RUN pip install /wheels/dist/*.whl && rm -rf /wheels

# Project code
COPY . /app/

# React SPA build (published to the spa_volume at container start so nginx
# can serve it — see deploy/docker-entrypoint.sh)
COPY --from=frontend-builder /frontend/dist /app/spa

# Runtime-writable dirs (media uploads); staticfiles is collected at startup
RUN mkdir -p /app/media /app/staticfiles && \
    chown -R app:app /app && \
    chmod +x /app/deploy/docker-entrypoint.sh

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz/ || exit 1

# Entrypoint: wait for DB → migrate → collectstatic → run command
ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]

# daphne: ASGI server (HTTP + WebSocket). `--proxy-headers` reads
# X-Forwarded-* from Nginx so remote IPs/HTTPS are correct.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "--proxy-headers", "config.asgi:application"]