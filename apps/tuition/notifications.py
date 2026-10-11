"""Tuition notifications: the reminder ladder and payment confirmation.

Delivery is idempotent twice over:

* every reminder attempt is keyed by ``PaymentReminderLog.idempotency_key``
  (UNIQUE), so a retried Celery task or a replayed scheduler tick cannot send a
  second reminder for the same (invoice, stage, recipient, channel);
* every message also reserves a ``NotificationLog.dedup_key`` before sending, so
  the transport-level audit cannot produce a duplicate either.

Recipients are the student themselves and their *verified, approved* parents.
Amounts come only from the stored invoice — a reminder never recalculates money.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.notifications.models import NotificationLog

from . import services
from .models import CourseInvoice, PaymentReminderLog

logger = logging.getLogger(__name__)


def _amount(value: Decimal | float | int) -> str:
    return f"{int(Decimal(value)):,}".replace(",", " ")


def reminder_text(invoice: CourseInvoice, stage: str) -> str:
    """The message body. Real recorded values only — no invented amounts."""
    student_name = invoice.student.get_full_name() or invoice.student.email
    balance = _amount(invoice.balance_uzs)
    due = f"{invoice.due_date:%d.%m.%Y}"
    if stage == PaymentReminderLog.Stage.BEFORE_DUE:
        head = f"⏰ {student_name}: kurs to'lovi muddati yaqinlashmoqda."
    elif stage == PaymentReminderLog.Stage.DUE_TODAY:
        head = f"📅 {student_name}: kurs to'lovi bugun to'lanishi kerak."
    elif stage == PaymentReminderLog.Stage.AWAITING_CONFIRMATION:
        return "\n".join([
            "GRANDEC — TO'LOV XABARNOMASI",
            "",
            f"{student_name} uchun to'lov topshirig'i qabul qilindi.",
            f"Tekshirilayotgan summa: {_amount(invoice.pending_amount_uzs)} so'm",
            "To'lov tasdiqlanishi bilan qoldiq yangilanadi.",
            "",
            "Qo'shimcha to'lov qilish shart emas.",
        ])
    else:
        head = f"❗️ {student_name}: kurs to'lovi muddati o'tgan."

    lines = [
        "GRANDEC — TO'LOV XABARNOMASI",
        "",
        head,
        f"Davr: {invoice.period_label or ''}",
        f"To'lanishi kerak: {_amount(invoice.amount_due_uzs)} so'm",
        f"Qoldiq: {balance} so'm",
        f"Muddat: {due}",
    ]
    if invoice.pending_amount_uzs > 0 and stage != PaymentReminderLog.Stage.AWAITING_CONFIRMATION:
        lines.append(
            f"Tekshirilayotgan to'lov: {_amount(invoice.pending_amount_uzs)} so'm"
        )
    policy = invoice.policy
    if policy and policy.payment_instructions:
        lines += ["", "To'lov bo'yicha ko'rsatma:", policy.payment_instructions]
    lines += ["", "Bu xabar faqat sizga yuboriladi."]
    return "\n".join(lines)


def _reserve_notification(*, recipient, title: str, message: str, dedup_key: str,
                          notification_type: str = NotificationLog.NotificationType.REMINDER):
    """Reserve the transport-level dedup key, or return ``None`` if already used."""
    try:
        with transaction.atomic():
            return NotificationLog.objects.create(
                recipient=recipient,
                channel=NotificationLog.Channel.TELEGRAM,
                notification_type=notification_type,
                title=title[:255],
                message=message,
                status=NotificationLog.Status.PENDING,
                dedup_key=dedup_key,
            )
    except IntegrityError:
        return None


def _send(chat_id: int, text: str, recipient, title: str) -> dict:
    from apps.notifications.services.telegram_service import TelegramService

    return TelegramService.send_message_with_keyboard(
        chat_id=chat_id, text=text, buttons=None,
        notification_type=NotificationLog.NotificationType.REMINDER,
        recipient=recipient, title=title,
    )


def send_reminder(invoice: CourseInvoice, stage: str, recipient, *,
                  channel: str = PaymentReminderLog.Channel.TELEGRAM,
                  transport=None) -> PaymentReminderLog:
    """Send (at most once) one reminder for one invoice stage to one recipient."""
    key = f"tuition:{invoice.pk}:{stage}:{recipient.pk}:{channel}"
    try:
        with transaction.atomic():
            log, created = PaymentReminderLog.objects.select_for_update().get_or_create(
                idempotency_key=key,
                defaults={
                    "invoice": invoice, "recipient": recipient, "stage": stage,
                    "channel": channel, "status": PaymentReminderLog.Status.PENDING,
                },
            )
    except IntegrityError:
        log = PaymentReminderLog.objects.get(idempotency_key=key)
        created = False
    #: Whether this call actually reached the transport. A caller must never
    #: report a re-seen SENT row as a fresh send.
    log.attempted = False
    if not created and log.status == PaymentReminderLog.Status.SENT:
        return log

    # Claim this durable reminder row before making network calls. A stale
    # pending reservation can be reclaimed after the same timeout used for a
    # Telegram send, while simultaneous workers return without sending twice.
    claim_time = timezone.now()
    stale_before = claim_time - timedelta(minutes=10)
    if not created:
        claimed = PaymentReminderLog.objects.filter(
            pk=log.pk, status=PaymentReminderLog.Status.PENDING,
            created_at__lt=stale_before,
        ).update(error="Stale send reservation reclaimed.")
        if not claimed and log.status == PaymentReminderLog.Status.PENDING:
            return log
        if claimed:
            log.error = "Stale send reservation reclaimed."

    text = reminder_text(invoice, stage)
    title = "Kurs to'lovi eslatmasi"
    chat_id = getattr(recipient, "telegram_chat_id", None)
    if channel == PaymentReminderLog.Channel.DASHBOARD:
        log.status = PaymentReminderLog.Status.SENT
        log.sent_at = timezone.now()
        log.error = ""
        log.save(update_fields=["status", "sent_at", "error"])
        log.attempted = True
        return log
    if not chat_id:
        # The web dashboard remains the delivery fallback; record Telegram
        # unavailability here, and let the distinct dashboard channel succeed.
        log.status = PaymentReminderLog.Status.FAILED
        log.error = "Telegram hisob ulanmagan; veb-panelda eslatma saqlandi."
        log.save(update_fields=["status", "error"])
        log.attempted = True
        return log

    # The reservation is the at-most-once *success* guarantee: a concurrent
    # worker loses this insert and backs off. It is released again if the send
    # fails, so a Telegram outage cannot permanently consume the key and block
    # every later retry of the same reminder.
    reserved = _reserve_notification(
        recipient=recipient, title=title, message=text, dedup_key=f"notif:{key}",
    )
    if reserved is None:
        prior = NotificationLog.objects.filter(dedup_key=f"notif:{key}").first()
        if prior and prior.status == NotificationLog.Status.SENT:
            log.status = PaymentReminderLog.Status.SENT
            log.sent_at = prior.created_at
            log.error = ""
            log.save(update_fields=["status", "sent_at", "error"])
            return log
        # Another task owns an in-flight reservation (or left a failed one).
        # Do not consume the reminder key; a later worker can safely claim it.
        log.status = PaymentReminderLog.Status.PENDING
        log.error = ""
        log.save(update_fields=["status", "error"])
        return log

    send = transport or _send
    try:
        result = send(chat_id, text, recipient, title)
    except Exception as exc:
        logger.exception("Tuition reminder failed for invoice %s", invoice.pk)
        result = {"success": False, "error": str(exc)}
    log.attempted = True
    if result and result.get("success"):
        log.status = PaymentReminderLog.Status.SENT
        log.sent_at = timezone.now()
        log.error = ""
        log.save(update_fields=["status", "sent_at", "error"])
        NotificationLog.objects.filter(pk=reserved.pk).update(
            status=NotificationLog.Status.SENT,
            external_id=str(result.get("message_id") or "")[:100],
            error_message="",
        )
    else:
        log.status = PaymentReminderLog.Status.FAILED
        log.error = str((result or {}).get("error") or "Noma'lum xatolik")[:2000]
        log.save(update_fields=["status", "error"])
        NotificationLog.objects.filter(pk=reserved.pk).delete()
    return log


def send_due_reminders(*, as_of: date | None = None, transport=None,
                       now=None) -> dict:
    """Run the reminder ladder for *as_of*, honouring preferences and quiet hours."""
    from apps.attendance.models import NotificationPreference
    from apps.weekly_reports.delivery import PREFERENCE_TUITION

    plan = services.reminders_due(as_of=as_of, now=now)
    sent = failed = skipped = duplicates = 0
    for item in plan:
        invoice = CourseInvoice.objects.select_related(
            "student", "policy",
        ).get(pk=item["invoice_id"])
        from django.contrib.auth import get_user_model

        recipient = get_user_model().objects.filter(pk=item["recipient_id"]).first()
        if recipient is None:
            continue
        preference = NotificationPreference.objects.filter(user=recipient).first()
        if preference is not None and (
            not getattr(preference, PREFERENCE_TUITION, True)
            or not getattr(preference, "telegram_enabled", True)
        ):
            skipped += 1
            continue
        log = send_reminder(
            invoice, item["stage"], recipient, transport=transport,
        )
        attempted = bool(getattr(log, "attempted", False))
        sent += attempted and log.status == PaymentReminderLog.Status.SENT
        failed += attempted and log.status == PaymentReminderLog.Status.FAILED
        skipped += attempted and log.status == PaymentReminderLog.Status.SKIPPED
        duplicates += not attempted
        if attempted and log.status in (
            PaymentReminderLog.Status.FAILED, PaymentReminderLog.Status.SKIPPED,
        ):
            # Dashboard is a separate fallback channel, not a transport attempt
            # included in the Telegram counters returned to job operators.
            send_reminder(
                invoice, item["stage"], recipient,
                channel=PaymentReminderLog.Channel.DASHBOARD,
            )
    return {
        "as_of": (as_of or services.today()).isoformat(),
        "planned": len(plan),
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "duplicates": duplicates,
    }


def send_payment_confirmed(invoice_id: int) -> dict:
    """Tell the student and their verified parents that a payment is confirmed.

    Runs ``on_commit`` from :func:`apps.tuition.services.verify_payment`, so the
    message can never describe a payment that rolled back.
    """
    invoice = CourseInvoice.objects.select_related("student", "policy").filter(
        pk=invoice_id,
    ).first()
    if invoice is None:
        return {"sent": 0}

    text = "\n".join([
        "GRANDEC — TO'LOV TASDIQLANDI",
        "",
        f"Davr: {invoice.period_label or ''}",
        f"Tasdiqlangan summa: {_amount(invoice.paid_amount_uzs)} so'm",
        f"Qoldiq: {_amount(invoice.balance_uzs)} so'm",
        f"Holat: {invoice.status_label}",
    ])
    sent = 0
    for recipient in services.reminder_recipients(invoice.student):
        key = f"tuition-confirmed:{invoice.pk}:{recipient.pk}"
        if _reserve_notification(
            recipient=recipient, title="Kurs to'lovi tasdiqlandi", message=text,
            dedup_key=key,
        ) is None:
            continue
        if not getattr(recipient, "telegram_chat_id", None):
            continue
        result = _send(
            recipient.telegram_chat_id, text, recipient, "Kurs to'lovi tasdiqlandi",
        )
        sent += 1 if (result or {}).get("success") else 0
    return {"sent": sent}
