"""Celery tasks for course tuition.

All three are idempotent, which is what lets beat restart, an operator re-run a
missed month, and a reminder ladder retry a failed Telegram send without
double-billing anyone or sending a duplicate notice.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from celery import shared_task
from django.utils.dateparse import parse_date

from . import notifications, services

logger = logging.getLogger(__name__)


def _parse(value: str | None) -> date | None:
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise ValueError("Sana formati noto'g'ri (YYYY-MM-DD kerak).")
    return parsed


@shared_task(
    bind=True,
    name="tuition.generate_monthly_invoices",
    max_retries=3,
    default_retry_delay=300,
    retry_backoff=True,
    retry_backoff_max=3600,
    retry_jitter=True,
    acks_late=True,
    time_limit=600,
    soft_time_limit=540,
)
def generate_monthly_invoices(self: Any, period_start: str | None = None,
                              dry_run: bool = False) -> dict[str, Any]:
    """Generate the month's invoices (idempotent per student/period/scope)."""
    try:
        reference = _parse(period_start) or services.today()
        result = services.generate_period_invoices(
            reference, dry_run=dry_run, reason="Oylik avtomatik hisoblash",
        )
        logger.info("Tuition invoicing: %s", result)
        return {"status": "completed", **result}
    except Exception as exc:
        logger.exception("Tuition invoice generation failed")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="tuition.mark_overdue_invoices",
    max_retries=3,
    default_retry_delay=300,
    retry_backoff=True,
    time_limit=300,
    soft_time_limit=240,
)
def mark_overdue_invoices(self: Any, as_of: str | None = None) -> dict[str, Any]:
    """Flag invoices past due (+grace). Never affects enrollment."""
    try:
        return {
            "status": "completed",
            **services.mark_overdue_invoices(as_of=_parse(as_of) or services.today()),
        }
    except Exception as exc:
        logger.exception("Overdue marking failed")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="tuition.send_payment_reminders",
    max_retries=3,
    default_retry_delay=600,
    retry_backoff=True,
    time_limit=600,
    soft_time_limit=540,
)
def send_payment_reminders(self: Any, as_of: str | None = None) -> dict[str, Any]:
    """Run the reminder ladder. Quiet hours and preferences are respected inside."""
    try:
        return {
            "status": "completed",
            **notifications.send_due_reminders(as_of=_parse(as_of) or services.today()),
        }
    except Exception as exc:
        logger.exception("Tuition reminder run failed")
        raise self.retry(exc=exc)
