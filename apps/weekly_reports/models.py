"""Weekly academic report storage, versioning and delivery bookkeeping.

Three concerns live here, deliberately separated:

* :class:`WeeklyReportSettings` — the administrator-configurable schedule. A
  single row (``pk=1``) so the Celery beat job and the website can never read
  two different schedules.
* :class:`WeeklyGroupReport` / :class:`WeeklyStudentReport` — the *persisted*
  summary of one closed reporting week, for one group or one student. A report
  is immutable once generated: correcting attendance or grading produces an
  explicit, versioned **new** row that supersedes the old one, so a teacher
  never sees a number change under their feet and an already-sent message can
  always be explained.
* :class:`WeeklyReportDelivery` — one row per (report, recipient, channel).
  ``dedup_key`` is UNIQUE, which is what makes a retried Celery task or a
  replayed scheduler tick unable to send the same Monday report twice.

No aggregation logic lives in the models; ``services.py`` owns it and both the
bot and the website call it.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

#: Weekday index used by the schedule (0 = Monday, matching ``date.weekday()``).
WEEKDAY_CHOICES = (
    (0, _("Dushanba")),
    (1, _("Seshanba")),
    (2, _("Chorshanba")),
    (3, _("Payshanba")),
    (4, _("Juma")),
    (5, _("Shanba")),
    (6, _("Yakshanba")),
)


class WeeklyReportSettings(models.Model):
    """Administrator-configurable weekly report schedule (singleton).

    The defaults are the documented Grandec defaults: reports cover the
    completed Monday–Sunday week in Asia/Tashkent and are sent on Monday at
    09:00. Changing the row changes the schedule — no redeploy required.
    """

    is_enabled = models.BooleanField(_("yoqilgan"), default=True)
    send_weekday = models.PositiveSmallIntegerField(
        _("yuborish kuni"), choices=WEEKDAY_CHOICES, default=0,
        help_text=_("0 = dushanba. Hisobot shu kuni yuboriladi."),
    )
    send_hour = models.PositiveSmallIntegerField(_("yuborish soati"), default=9)
    send_minute = models.PositiveSmallIntegerField(_("yuborish daqiqasi"), default=0)
    timezone_name = models.CharField(
        _("vaqt zonasi"), max_length=64, default="Asia/Tashkent",
    )
    #: Local Monday corresponding to the last scheduled week claimed/completed.
    #: The periodic scheduler uses this cursor for catch-up after outages.
    last_scheduled_period_start = models.DateField(
        null=True, blank=True, editable=False,
    )
    last_schedule_started_at = models.DateTimeField(
        null=True, blank=True, editable=False,
    )
    #: Last task execution status retained for the operations dashboard.
    last_schedule_status = models.CharField(
        max_length=24, blank=True, default="",
    )
    #: Whether the *sending* job also (re)tries deliveries that previously
    #: failed — an operator can switch this off during an incident.
    retry_failed_deliveries = models.BooleanField(
        _("xatoliklarni qayta urinish"), default=True,
    )
    #: How many delivery attempts a single report may accumulate.
    max_delivery_attempts = models.PositiveSmallIntegerField(
        _("maksimal urinishlar"), default=5,
    )
    #: Administrators who explicitly asked for the platform-wide digest. Without
    #: this, every group report would be pushed to every administrator, which is
    #: noise — and noise is how a real alert gets ignored.
    admin_recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="weekly_report_admin_subscriptions",
        verbose_name=_("administrator qabul qiluvchilar"),
    )
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weekly_report_settings_updates",
        verbose_name=_("o'zgartirgan"),
    )

    class Meta:
        verbose_name = _("Haftalik hisobot sozlamasi")
        verbose_name_plural = _("Haftalik hisobot sozlamalari")

    def __str__(self) -> str:
        state = "yoqilgan" if self.is_enabled else "o'chirilgan"
        return f"Haftalik hisobot: {state}"

    def save(self, *args, **kwargs) -> None:
        # Singleton: every write lands on pk=1 so two rows can never disagree.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> WeeklyReportSettings:
        """Return the settings row, creating it with defaults if absent."""
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class ReportPeriodMixin(models.Model):
    """Shared period/version bookkeeping for both report kinds."""

    period_start = models.DateTimeField(
        _("davr boshlanishi"), db_index=True,
        help_text=_("Mahalliy vaqtda dushanba 00:00."),
    )
    period_end = models.DateTimeField(
        _("davr tugashi"),
        help_text=_("Mahalliy vaqtda yakshanba 23:59:59.999999 (inklyuziv)."),
    )
    period_label = models.CharField(_("davr"), max_length=64, blank=True)
    version = models.PositiveIntegerField(_("versiya"), default=1)
    #: Only one version per (object, period) is current. An old version is kept
    #: forever for audit — a report is a record of what was actually reported.
    is_current = models.BooleanField(_("joriy versiya"), default=True, db_index=True)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superseded_by",
        verbose_name=_("o'rnini bosgan hisobot"),
    )
    generation_reason = models.CharField(_("sabab"), max_length=200, blank=True)
    status = models.CharField(
        _("holat"), max_length=20,
        choices=(
            ("generated", _("Tayyorlangan")),
            ("sent", _("Yuborilgan")),
            ("failed", _("Yuborilmadi")),
        ),
        default="generated",
        db_index=True,
    )
    summary = models.JSONField(_("xulosa"), default=dict, blank=True)
    generated_at = models.DateTimeField(_("tayyorlangan"), auto_now_add=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_generated",
        verbose_name=_("tayyorlagan"),
        help_text=_("Bo'sh bo'lsa — rejalashtiruvchi (Celery beat)."),
    )

    class Meta:
        abstract = True


class WeeklyGroupReport(ReportPeriodMixin):
    """One closed week's summary for one teacher group."""

    group = models.ForeignKey(
        "courses.StudentGroup",
        on_delete=models.CASCADE,
        related_name="weekly_reports",
        verbose_name=_("guruh"),
    )

    class Meta:
        verbose_name = _("Guruh haftalik hisoboti")
        verbose_name_plural = _("Guruh haftalik hisobotlari")
        ordering = ["-period_start", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "period_start", "version"],
                name="uniq_weekly_group_report_version",
            ),
        ]
        indexes = [
            models.Index(fields=["group", "period_start"], name="idx_wgrp_period"),
        ]

    def __str__(self) -> str:
        return f"{self.group.name} · {self.period_label or self.period_start:%Y-%m-%d} (v{self.version})"


class WeeklyStudentReport(ReportPeriodMixin):
    """One closed week's summary for a single student (parent-facing)."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_reports",
        verbose_name=_("o'quvchi"),
    )

    class Meta:
        verbose_name = _("O'quvchi haftalik hisoboti")
        verbose_name_plural = _("O'quvchi haftalik hisobotlari")
        ordering = ["-period_start", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "period_start", "version"],
                name="uniq_weekly_student_report_version",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} · {self.period_label or self.period_start:%Y-%m-%d} (v{self.version})"


class WeeklyReportDelivery(models.Model):
    """One delivery attempt record per (report, recipient, channel).

    ``dedup_key`` is UNIQUE, and the *same* key is reused on retry, so a redelivery
    replaces the status of the existing row instead of creating a second message.
    """

    class Channel(models.TextChoices):
        TELEGRAM = "telegram", _("Telegram")
        DASHBOARD = "dashboard", _("Veb-panel")

    class Status(models.TextChoices):
        PENDING = "pending", _("Kutilmoqda")
        SENT = "sent", _("Yuborildi")
        FAILED = "failed", _("Xatolik")
        SKIPPED = "skipped", _("O'tkazib yuborildi")
        #: Telegram is unreachable; the report stays readable in the dashboard.
        DEFERRED = "deferred", _("Keyinroq")

    report = models.ForeignKey(
        WeeklyGroupReport,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="deliveries",
        verbose_name=_("guruh hisoboti"),
    )
    student_report = models.ForeignKey(
        WeeklyStudentReport,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="deliveries",
        verbose_name=_("o'quvchi hisoboti"),
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_report_deliveries",
        verbose_name=_("qabul qiluvchi"),
    )
    channel = models.CharField(
        _("kanal"), max_length=20, choices=Channel.choices,
        default=Channel.TELEGRAM,
    )
    status = models.CharField(
        _("holat"), max_length=20, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    dedup_key = models.CharField(_("idempotentlik kaliti"), max_length=200, unique=True)
    telegram_message_id = models.CharField(
        _("Telegram xabar ID"), max_length=64, blank=True,
    )
    retry_count = models.PositiveIntegerField(_("urinishlar"), default=0)
    last_error = models.TextField(_("oxirgi xatolik"), blank=True)
    last_attempt_at = models.DateTimeField(_("oxirgi urinish"), null=True, blank=True)
    sent_at = models.DateTimeField(_("yuborilgan"), null=True, blank=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Hisobot yuborilishi")
        verbose_name_plural = _("Hisobot yuborilishlari")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                # Exactly one report kind: a group report or a student report,
                # never both and never neither.
                condition=(
                    models.Q(report__isnull=False, student_report__isnull=True)
                    | models.Q(report__isnull=True, student_report__isnull=False)
                ),
                name="weekly_delivery_exactly_one_report",
            ),
        ]
        indexes = [
            models.Index(fields=["recipient", "status"], name="idx_wdeliv_recip"),
        ]

    def __str__(self) -> str:
        return f"{self.recipient_id} · {self.channel} · {self.status}"

    @property
    def target(self):
        """The group report or student report this delivery belongs to."""
        return self.report if self.report_id else self.student_report

    def mark_sent(self, message_id: str = "") -> None:
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.last_attempt_at = self.sent_at
        self.last_error = ""
        if message_id:
            self.telegram_message_id = str(message_id)[:64]
        self.save(update_fields=[
            "status", "sent_at", "last_attempt_at", "last_error",
            "telegram_message_id",
        ])
