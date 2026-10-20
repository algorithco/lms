"""Privacy-preserving metrics for the shared essay grading cache (Phase M).

Counters are process-local (one per web process / Celery worker) and are also
emitted as structured log lines, so an operator can compute cache hit rate and
avoided AI requests without a new metrics backend.

What is deliberately NOT recorded: essay text, API keys, student identity,
teacher comments. Only opaque cache keys, scores, durations and event names.
"""

from __future__ import annotations

import logging
import threading
from collections import Counter

logger = logging.getLogger("apps.essays.metrics")

#: Events emitted by the shared grading cache lifecycle.
CACHE_EVENTS = (
    "hit",  # a completed evaluation was reused
    "miss",  # no reusable evaluation existed
    "leader_claimed",  # this worker reserved the single AI operation
    "dedup_wait",  # another worker owns the operation (waiting)
    "reuse",  # a waiter received the leader's evaluation
    "distributed",  # a waiting submission was completed
    "completed",  # canonical evaluation persisted
    "failed",  # provider/pipeline failure (never cached)
    "provider_failure",  # AI provider raised
    "context_mismatch",  # key collided on text but not on grading context
    "bypass_scope",  # restricted/high-stakes assessment: no reuse
    "lease_lost",  # lease expired before completion; not overwritten
    "stale_lease_recovered",  # abandoned PROCESSING lease released
    "entry_discarded",  # corrupt/obsolete payload dropped
    "invalidated",  # admin invalidation
    "purged",  # obsolete rows deleted
    "ai_request",  # a paid AI grading request was made
)

_lock = threading.Lock()
_counters: Counter[str] = Counter()


def cache_event(event: str, **fields) -> None:
    """Count and log one cache lifecycle event (never raises)."""
    try:
        with _lock:
            _counters[f"essay_cache_{event}"] += 1
        logger.info(
            "essay_cache_event event=%s%s",
            event,
            "".join(f" {k}={v}" for k, v in sorted(fields.items())),
        )
    except Exception:  # pragma: no cover - metrics must never break grading
        logger.debug("Failed to record essay cache metric: %s", event, exc_info=True)


def snapshot() -> dict[str, int]:
    """Current counter values (tests and admin diagnostics)."""
    with _lock:
        return dict(_counters)


def reset() -> None:
    """Clear counters (tests)."""
    with _lock:
        _counters.clear()


def get_counter(event: str) -> int:
    with _lock:
        return _counters.get(f"essay_cache_{event}", 0)


def cache_hit_rate() -> float:
    """Hits / (hits + misses) as a 0..1 fraction (0.0 when no observations)."""
    hits = get_counter("hit")
    misses = get_counter("miss")
    total = hits + misses
    return round(hits / total, 4) if total else 0.0
