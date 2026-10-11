"""Celery tasks for automated weekly academic reports.

Every task here is safe to run twice: generation is unique per
(group, period, version) and delivery is unique per ``dedup_key``. That is what
makes an aggressive retry policy, a beat restart or a manual "run it again"
during an incident recover a missed week instead of duplicating it.

The optional ``period_start``/``period_end`` arguments exist precisely for that
recovery path — the beat schedule itself always reports on the *completed*
previous week, so an incomplete week is never published as final.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import delivery, services
from .models import WeeklyReportSettings

logger = logging.getLogger(__name__)


def _resolve_period(period_start: str | None, period_end: str | None):
    if period_start and period_end:
        start = parse_datetime(period_start)
        end = parse_datetime(period_end)
        if start is None or end is None:
            raise ValueError("Sana formati noto'g'ri (ISO-8601 kerak).")
        if timezone.is_naive(start):
            start = timezone.make_aware(start, services.reporting_timezone())
        if timezone.is_naive(end):
            end = timezone.make_aware(end, services.reporting_timezone())
        return start, end
    return services.previous_week_bounds()


@shared_task(
    bind=True,
    name="weekly_reports.generate_and_send",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=900,
    retry_jitter=True,
    acks_late=True,
    time_limit=600,
    soft_time_limit=540,
)
def generate_and_send_weekly_reports(self: Any, period_start: str | None = None,
                                     period_end: str | None = None) -> dict[str, Any]:
    """Generate the completed week's reports and deliver them once."""
    config = WeeklyReportSettings.load()
    if not config.is_enabled:
        logger.info("Weekly reports are disabled; skipping.")
        return {"status": "disabled"}

    try:
        current = timezone.now()
        if period_start is None and period_end is None:
            local = current.astimezone(services.reporting_timezone())
            configured_time = (int(config.send_hour), int(config.send_minute))
            due = local.weekday() > int(config.send_weekday) or (
                local.weekday() == int(config.send_weekday)
                and (local.hour, local.minute) >= configured_time
            )
            if not due:
                return {"status": "not_due"}
            # Runs every few minutes, not at a hard-coded Monday 09:00, so an
            # admin's saved weekday/time takes effect without redeploying Beat.
            latest_start, _latest_end = services.week_bounds(local - timedelta(days=7))
            latest_local_start = latest_start.astimezone(
                services.reporting_timezone(),
            ).date()
            cursor = config.last_scheduled_period_start
            if cursor and cursor > latest_local_start:
                return {"status": "already_processed", "period_start": latest_start.isoformat()}
            if cursor == latest_local_start and config.last_schedule_status == "completed":
                return {"status": "already_processed", "period_start": latest_start.isoformat()}
            if (
                cursor == latest_local_start
                and config.last_schedule_status == "running"
                and config.last_schedule_started_at
                and current - config.last_schedule_started_at < timedelta(minutes=15)
            ):
                return {"status": "already_running", "period_start": latest_start.isoformat()}

            # If the cursor is this same week but its prior attempt failed or
            # got stale, replay it. Otherwise advance exactly one missing week
            # at a time so a prolonged outage can be recovered in sequence.
            candidate_date = cursor + timedelta(days=7) if cursor and cursor < latest_local_start else latest_local_start
            if cursor == latest_local_start:
                start, end = latest_start, _latest_end
            else:
                anchor = datetime.combine(
                    candidate_date, datetime.min.time(),
                    tzinfo=services.reporting_timezone(),
                )
                start, end = services.week_bounds(anchor)
        else:
            start, end = _resolve_period(period_start, period_end)

        if period_start is None and period_end is None:
            # Claim the reporting week before doing external sends. Concurrent
            # Beat workers see the cursor and cannot dispatch it twice. If the
            # task dies, retry_deliveries plus idempotent report generation
            # recover persistent delivery rows.
            with transaction.atomic():
                locked = WeeklyReportSettings.objects.select_for_update().get(pk=1)
                claimed_date = start.astimezone(
                    services.reporting_timezone(),
                ).date()
                if (
                    locked.last_scheduled_period_start == claimed_date
                    and locked.last_schedule_status == "completed"
                ):
                    return {"status": "already_processed", "period_start": start.isoformat()}
                if (
                    locked.last_scheduled_period_start == claimed_date
                    and locked.last_schedule_status == "running"
                    and locked.last_schedule_started_at
                    and current - locked.last_schedule_started_at < timedelta(minutes=15)
                ):
                    return {"status": "already_running", "period_start": start.isoformat()}
                locked.last_scheduled_period_start = claimed_date
                locked.last_schedule_started_at = current
                locked.last_schedule_status = "running"
                locked.save(update_fields=[
                    "last_scheduled_period_start", "last_schedule_started_at",
                    "last_schedule_status", "updated_at",
                ])
            config = locked

        generated = services.generate_all_reports(start, end)
        sent = delivery.send_reports(start, end)
        if period_start is None and period_end is None:
            WeeklyReportSettings.objects.filter(pk=1).update(
                last_schedule_status="completed",
            )
            if start.astimezone(services.reporting_timezone()).date() < latest_local_start:
                # Only queue the next missed period after this one has a
                # terminal generation/delivery pass; the next poll still
                # verifies no incomplete week is selected.
                self.apply_async(countdown=1)
        return {"status": "completed", **generated, **sent}
    except Exception as exc:
        logger.exception("Weekly report job failed")
        if period_start is None and period_end is None:
            WeeklyReportSettings.objects.filter(pk=1).update(
                last_schedule_status="failed",
            )
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="weekly_reports.generate_only",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=900,
    retry_jitter=True,
    time_limit=600,
    soft_time_limit=540,
)
def generate_weekly_reports(self: Any, period_start: str | None = None,
                            period_end: str | None = None) -> dict[str, Any]:
    """Generate (never send) — used to pre-warm reports for the dashboard."""
    try:
        start, end = _resolve_period(period_start, period_end)
        return {"status": "completed", **services.generate_all_reports(start, end)}
    except Exception as exc:
        logger.exception("Weekly report generation failed")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="weekly_reports.retry_deliveries",
    max_retries=2,
    default_retry_delay=120,
    time_limit=300,
    soft_time_limit=240,
)
def retry_weekly_report_deliveries(self: Any, limit: int = 100) -> dict[str, Any]:
    """Recover deliveries that failed because Telegram was unreachable."""
    try:
        return {"status": "completed", **delivery.retry_failed_deliveries(limit=limit)}
    except Exception as exc:
        logger.exception("Weekly report retry failed")
        raise self.retry(exc=exc)
