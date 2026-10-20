"""Attendance, classroom observations and group notification routing.

This is a NEW domain: before it existed Grandec had teacher groups
(``courses.StudentGroup``) and parent links (``accounts.ParentStudentLink``) but
no way to record who attended a lesson. Everything here is additive and reuses
those canonical models rather than introducing parallel group/parent concepts.

Privacy model (enforced by the services, not just the API):

* A teacher may only read/write attendance for groups they own.
* Named student attendance reaches a parent **only** in a verified private chat
  with an approved ``ParentStudentLink``.
* Shared Telegram destinations receive aggregate, non-identifying summaries
  (see :class:`GroupNotificationDestination`), and only when an administrator
  has approved the destination.
* Classroom observations are neutral teacher notes. They are never sent to a
  parent until the recording teacher explicitly confirms them, and they never
  carry a humiliating label or an automatic punishment.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------


class AttendanceSession(models.Model):
    """One lesson's attendance register for one teacher group.

    A group can legitimately have several sessions in a day (double periods,
    morning/evening shifts), so uniqueness is on
    ``(group, lesson_date, start_time)`` rather than on the date alone.
    ``idempotency_key`` lets the Telegram flow replay a callback without
    creating a second register.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Qoralama")
        FINALIZED = "finalized", _("Yakunlangan")
        CANCELLED = "cancelled", _("Bekor qilingan")

    group = models.ForeignKey(
        "courses.StudentGroup",
        on_delete=models.CASCADE,
        related_name="attendance_sessions",
        verbose_name=_("guruh"),
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_sessions",
        verbose_name=_("o'qituvchi"),
    )
    lesson_date = models.DateField(_("dars sanasi"), db_index=True)
    start_time = models.TimeField(_("boshlanish vaqti"), null=True, blank=True)
    end_time = models.TimeField(_("tugash vaqti"), null=True, blank=True)
    status = models.CharField(
        _("holat"),
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    #: Optional free-text label ("1-dars", "Nazorat ishi").
    title = models.CharField(_("izoh"), max_length=120, blank=True)
    idempotency_key = models.CharField(
        _("idempotentlik kaliti"),
        max_length=120,
        unique=True,
        null=True,
        blank=True,
        help_text=_("Bot callback'ini takror yuborishda dublikat yaratmaslik uchun."),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_attendance_sessions",
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)
    finalized_at = models.DateTimeField(_("yakunlangan vaqt"), null=True, blank=True)
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finalized_attendance_sessions",
    )

    class Meta:
        verbose_name = _("Davomat darsi")
        verbose_name_plural = _("Davomat darslari")
        ordering = ["-lesson_date", "-start_time", "-id"]
        constraints = [
            # One register per group/date/start time. NULL start times are
            # allowed to repeat on PostgreSQL and SQLite alike, so a dated
            # session without a period remains expressible.
            models.UniqueConstraint(
                fields=["group", "lesson_date", "start_time"],
                name="uniq_attendance_session_slot",
            ),
        ]
        indexes = [
            models.Index(fields=["group", "lesson_date"], name="idx_att_group_date"),
            models.Index(
                fields=["teacher", "lesson_date"], name="idx_att_teacher_date"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.group_id}@{self.lesson_date} ({self.status})"

    @property
    def is_finalized(self) -> bool:
        return self.status == self.Status.FINALIZED

    @property
    def local_start(self):
        """Session start as an aware datetime in the configured local timezone."""
        if self.start_time is None:
            return None
        naive = timezone.datetime.combine(self.lesson_date, self.start_time)
        return timezone.make_aware(naive, timezone.get_current_timezone())

    def local_time_label(self) -> str:
        """``14:30`` in Uzbekistan local time, or ``—`` when unscheduled."""
        if self.start_time is None:
            return "—"
        return timezone.localtime(self.local_start).strftime("%H:%M")


class AttendanceRecord(models.Model):
    """One student's status inside one attendance session (unique pair)."""

    class Status(models.TextChoices):
        PRESENT = "present", _("Keldi")
        ABSENT = "absent", _("Kelmadi")
        LATE = "late", _("Kechikdi")
        EXCUSED = "excused", _("Sababli")

    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name="records",
        verbose_name=_("davomat darsi"),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
        verbose_name=_("o'quvchi"),
    )
    status = models.CharField(
        _("holat"),
        max_length=16,
        choices=Status.choices,
        db_index=True,
    )
    late_minutes = models.PositiveIntegerField(_("kechikish (daqiqa)"), default=0)
    note = models.CharField(_("izoh"), max_length=200, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_attendance_records",
    )
    marked_at = models.DateTimeField(_("belgilangan vaqt"), default=timezone.now)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Davomat yozuvi")
        verbose_name_plural = _("Davomat yozuvlari")
        ordering = ["student__first_name", "student__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "student"],
                name="uniq_attendance_record_per_student",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "status"], name="idx_att_student_status"),
        ]

    def __str__(self) -> str:
        return f"{self.student_id}:{self.status}"


class AttendanceAuditLog(models.Model):
    """Append-only audit trail for attendance corrections.

    Marking and re-marking is normal teacher behaviour, so the log records the
    transition (actor, field, old/new value, reason) rather than blocking it.
    """

    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_actions",
    )
    field = models.CharField(_("maydon"), max_length=32, default="status")
    old_value = models.CharField(max_length=200, blank=True)
    new_value = models.CharField(max_length=200, blank=True)
    reason = models.CharField(_("sabab"), max_length=200, blank=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Davomat tuzatish tarixi")
        verbose_name_plural = _("Davomat tuzatish tarixlari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.student_id}: {self.old_value}->{self.new_value}"


# ---------------------------------------------------------------------------
# Classroom observations
# ---------------------------------------------------------------------------


class ClassroomObservation(models.Model):
    """A teacher's neutral note about classroom conduct.

    Deliberately *not* a disciplinary record: no automatic punishment, no
    ranking, and nothing reaches a parent until the teacher confirms it.
    """

    class ObservationType(models.TextChoices):
        PARTICIPATION = (
            "participation_needs_attention",
            _("Faollik e'tibor talab qiladi"),
        )
        RULES = "classroom_rules_reminder", _("Sinf qoidalari eslatmasi")
        POSITIVE = "positive_participation", _("Ijobiy faollik")
        NOTE = "teacher_note", _("O'qituvchi izohi")

    class NotificationStatus(models.TextChoices):
        NOT_SENT = "not_sent", _("Yuborilmagan")
        PENDING_CONFIRMATION = "pending_confirmation", _("Tasdiq kutilmoqda")
        SENT = "sent", _("Yuborilgan")
        SKIPPED = "skipped", _("Yuborilmadi (o'qituvchi rad etdi)")

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="classroom_observations",
    )
    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="observations",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recorded_observations",
    )
    observation_type = models.CharField(
        _("turi"),
        max_length=40,
        choices=ObservationType.choices,
    )
    neutral_description = models.TextField(_("neytral izoh"))
    notification_status = models.CharField(
        _("xabar holati"),
        max_length=24,
        choices=NotificationStatus.choices,
        default=NotificationStatus.NOT_SENT,
        db_index=True,
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_observations",
    )
    confirmed_at = models.DateTimeField(_("tasdiqlangan vaqt"), null=True, blank=True)
    sent_at = models.DateTimeField(_("yuborilgan vaqt"), null=True, blank=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Sinf kuzatuvi")
        verbose_name_plural = _("Sinf kuzatuvlari")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "created_at"], name="idx_obs_student"),
        ]

    def __str__(self) -> str:
        return f"{self.student_id}:{self.observation_type}"

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None


# ---------------------------------------------------------------------------
# Notification routing
# ---------------------------------------------------------------------------


class GroupNotificationDestination(models.Model):
    """An administrator-approved Telegram destination for group notices.

    A chat id is never trusted because a teacher typed it: the row must be
    ``is_approved`` (with a named approver) before anything is delivered.
    ``STAFF`` destinations may receive named student information;
    ``PARENT_PUBLIC`` destinations only ever receive aggregate summaries.
    """

    class DestinationType(models.TextChoices):
        STAFF = "staff", _("Xodimlar guruhi")
        PARENT_PUBLIC = "parent_public", _("Ota-onalar / umumiy guruh")

    group = models.ForeignKey(
        "courses.StudentGroup",
        on_delete=models.CASCADE,
        related_name="notification_destinations",
        null=True,
        blank=True,
        help_text=_("Bo'sh bo'lsa — barcha guruhlar uchun umumiy manzil."),
    )
    chat_id = models.BigIntegerField(_("Telegram chat ID"))
    title = models.CharField(_("nomi"), max_length=150, blank=True)
    destination_type = models.CharField(
        _("manzil turi"),
        max_length=20,
        choices=DestinationType.choices,
        default=DestinationType.PARENT_PUBLIC,
        db_index=True,
    )
    is_enabled = models.BooleanField(_("yoqilgan"), default=True)
    is_approved = models.BooleanField(_("tasdiqlangan"), default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_notification_destinations",
    )
    approved_at = models.DateTimeField(_("tasdiqlangan vaqt"), null=True, blank=True)
    #: Categories this destination accepts, e.g. ``["attendance_summary"]``.
    allowed_categories = models.JSONField(
        _("ruxsat etilgan toifalar"), default=list, blank=True
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Guruh xabar manzili")
        verbose_name_plural = _("Guruh xabar manzillari")
        ordering = ["group__name", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "chat_id"],
                name="uniq_destination_group_chat",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_destination_type_display()}: {self.chat_id}"

    @property
    def is_usable(self) -> bool:
        return bool(self.is_enabled and self.is_approved)

    def accepts(self, category: str) -> bool:
        if not self.is_usable:
            return False
        allowed = self.allowed_categories or []
        return category in allowed


class NotificationPreference(models.Model):
    """Per-user opt-in/out switches for non-essential notifications.

    All events that concern a user's own account or their own child default to
    ON; a user can switch off the optional ones.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preference",
    )
    telegram_enabled = models.BooleanField(_("Telegram xabarlari"), default=True)
    # Student / parent facing
    attendance_alerts = models.BooleanField(_("Davomat xabarlari"), default=True)
    essay_graded_alerts = models.BooleanField(_("Esse bahosi xabarlari"), default=True)
    test_result_alerts = models.BooleanField(_("Test natijasi xabarlari"), default=True)
    observation_alerts = models.BooleanField(
        _("Kuzatuv xabarlari (tasdiqlangandan keyin)"),
        default=True,
    )
    # Teacher facing
    teacher_new_essay = models.BooleanField(_("Yangi esse topshirildi"), default=True)
    teacher_grading_completed = models.BooleanField(_("Esse baholandi"), default=True)
    teacher_grading_failed = models.BooleanField(
        _("Esse baholashda xatolik"), default=True
    )
    teacher_attendance_reminder = models.BooleanField(
        _("Davomat yakunlanmagan eslatmasi"),
        default=True,
    )
    # Weekly report digest (optional — a recipient may switch it off)
    teacher_weekly_report = models.BooleanField(
        _("Haftalik guruh hisoboti (o'qituvchi)"),
        default=True,
    )
    parent_weekly_report = models.BooleanField(
        _("Haftalik farzand hisoboti (ota-ona)"),
        default=True,
    )
    # Course tuition reminders (separate from platform subscription notices)
    tuition_reminders = models.BooleanField(
        _("Kurs to'lovi eslatmalari"),
        default=True,
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Xabar sozlamasi")
        verbose_name_plural = _("Xabar sozlamalari")

    def __str__(self) -> str:
        return f"Prefs({self.user_id})"

    @classmethod
    def for_user(cls, user) -> "NotificationPreference":
        if user is None or not getattr(user, "pk", None):
            raise ValueError("A saved user is required.")
        preference, _ = cls.objects.get_or_create(user=user)
        return preference
