"""
Core tasks — automated cleanup & maintenance.

Runs via Celery Beat schedule:
    1. cleanup_expired_sessions  — remove expired Django sessions
    2. cleanup_stale_attempts    — mark abandoned IN_PROGRESS attempts as TIMEOUT
    3. cleanup_cache_entries     — flush stale cache keys
    4. daily_maintenance         — orchestrator that runs all cleanup tasks

These tasks prevent database bloat and keep the system performant.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Cleanup expired sessions
# ---------------------------------------------------------------------------

@shared_task(
    name="core.cleanup_expired_sessions",
    acks_late=True,
)
def cleanup_expired_sessions() -> dict[str, Any]:
    """
    Remove expired Django sessions from the session store.

    This prevents the django_session table from growing indefinitely.
    Django's `clearsessions` management command handles this.
    """
    from django.contrib.sessions.models import Session

    before_count = Session.objects.count()

    # Remove sessions with expired expiry_date
    Session.objects.filter(expire_date__lt=timezone.now()).delete()

    after_count = Session.objects.count()
    removed = before_count - after_count

    logger.info(
        "Sessions cleanup: removed %d expired sessions (%d remaining)",
        removed, after_count,
    )

    return {
        "status": "completed",
        "removed": removed,
        "remaining": after_count,
    }


# ---------------------------------------------------------------------------
# 2. Cleanup stale (abandoned) test attempts
# ---------------------------------------------------------------------------

@shared_task(
    name="core.check_timeout_attempts",
    acks_late=True,
    time_limit=55,
)
def check_timeout_attempts() -> dict[str, Any]:
    """Finalize attempts whose configured test deadline has passed."""
    from apps.tests.models import TestAttempt
    from apps.tests.services import SubmitAttemptService

    attempts = TestAttempt.objects.filter(
        status=TestAttempt.Status.IN_PROGRESS,
        test__time_limit_minutes__gt=0,
    ).select_related("test", "student")
    completed = 0
    errors = 0
    for attempt in attempts.iterator(chunk_size=200):
        if not attempt.is_time_expired:
            continue
        try:
            SubmitAttemptService.execute(attempt.id, attempt.student)
            completed += 1
        except ValueError:
            # A concurrent request may already have finalized it.
            continue
        except Exception:
            errors += 1
            logger.exception("Failed to finalize timed-out attempt: id=%d", attempt.id)
    return {"status": "completed", "completed": completed, "errors": errors}

@shared_task(
    name="core.cleanup_stale_attempts",
    acks_late=True,
    time_limit=300,
    soft_time_limit=240,
)
def cleanup_stale_attempts() -> dict[str, Any]:
    """
    Mark abandoned IN_PROGRESS attempts as TIMEOUT.

    Criteria: attempt started more than 2x the time_limit ago
    and is still IN_PROGRESS. This handles cases where:
    - User closed browser without submitting
    - Celery timeout task didn't fire
    - Network disconnection
    """
    from apps.tests.models import TestAttempt
    from apps.tests.services import SubmitAttemptService

    now = timezone.now()
    stale_threshold = now - timedelta(hours=6)  # anything older than 6 hours

    stale_attempts = TestAttempt.objects.filter(
        status=TestAttempt.Status.IN_PROGRESS,
        started_at__lt=stale_threshold,
    ).select_related("test", "student")

    cleaned = 0
    errors = 0

    for attempt in stale_attempts:
        try:
            # Check if time limit has also passed
            if attempt.is_time_expired:
                SubmitAttemptService._timeout_attempt(attempt)
                cleaned += 1
                logger.info(
                    "Stale attempt cleaned: id=%d, test=%d, student=%d, started=%s",
                    attempt.id, attempt.test_id, attempt.student_id, attempt.started_at,
                )
        except Exception:
            errors += 1
            logger.error(
                "Failed to clean stale attempt: id=%d", attempt.id, exc_info=True,
            )

    logger.info(
        "Stale attempts cleanup: cleaned=%d, errors=%d", cleaned, errors,
    )

    return {
        "status": "completed",
        "cleaned": cleaned,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 3. Cleanup stale cache entries
# ---------------------------------------------------------------------------

@shared_task(
    name="core.cleanup_cache",
    acks_late=True,
)
def cleanup_cache_entries() -> dict[str, Any]:
    """
    Flush known stale cache keys.

    Django's default cache backend (LocMem) doesn't auto-expire keys.
    This task cleans up dashboard caches that may be stale.
    """
    patterns_to_clear = [
        "student_dashboard_*",
        "teacher_dashboard_*",
        "test_list_*",
        "cert_verify_*",
        "games_hub_etag_*",
    ]

    cleared = 0

    # For LocMem cache, we can't iterate keys.
    # For Redis, we could use SCAN + DELETE.
    # Strategy: try to clear specific known patterns.
    try:
        # Clear all dashboard caches (they're regenerated on next request)
        cache.clear()
        cleared = 1
        logger.info("Cache cleared entirely (LocMem backend)")
    except Exception:
        logger.warning("Cache clear failed", exc_info=True)

    return {
        "status": "completed",
        "cleared": cleared,
    }


# ---------------------------------------------------------------------------
# 4. Daily maintenance orchestrator
# ---------------------------------------------------------------------------

@shared_task(
    name="core.daily_maintenance",
    acks_late=True,
    time_limit=600,
    soft_time_limit=540,
)
def daily_maintenance() -> dict[str, Any]:
    """
    Run all maintenance tasks sequentially.

    Scheduled via Celery Beat: daily at 3:00 AM (low-traffic period).
    """
    logger.info("Starting daily maintenance tasks...")

    results = {}

    # 1. Session cleanup
    try:
        results["sessions"] = cleanup_expired_sessions()
    except Exception as e:
        logger.error("Session cleanup failed: %s", e)
        results["sessions"] = {"status": "error", "message": str(e)}

    # 2. Stale attempts cleanup
    try:
        results["stale_attempts"] = cleanup_stale_attempts()
    except Exception as e:
        logger.error("Stale attempts cleanup failed: %s", e)
        results["stale_attempts"] = {"status": "error", "message": str(e)}

    # 3. Cache cleanup
    try:
        results["cache"] = cleanup_cache_entries()
    except Exception as e:
        logger.error("Cache cleanup failed: %s", e)
        results["cache"] = {"status": "error", "message": str(e)}

    logger.info("Daily maintenance completed: %s", results)

    return {
        "status": "completed",
        "tasks": results,
    }
