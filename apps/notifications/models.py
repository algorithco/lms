"""
Notifications app — Telegram Bot integration and notification logging.

Models:
    NotificationLog — audit trail for every notification sent.
"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


# The website, bot, and status endpoint must all use the same lifetime.
TELEGRAM_AUTH_TOKEN_TTL = timedelta(minutes=10)


# ---------------------------------------------------------------------------
# NotificationLog
# ---------------------------------------------------------------------------
class NotificationLog(models.Model):
    """
    Immutable log of every notification sent via any channel.

    This is the audit trail — once a message is sent (or attempted),
    a record is written here regardless of success or failure.
    """

    class Channel(models.TextChoices):
        TELEGRAM = "telegram", _("Telegram")
        EMAIL = "email", _("Email")

    class Status(models.TextChoices):
        PENDING = "pending", _("Kutilmoqda")
        SENT = "sent", _("Yuborildi")
        FAILED = "failed", _("Xatolik")

    class NotificationType(models.TextChoices):
        TEST_RESULT = "test_result", _("Test natijasi")
        CERTIFICATE = "certificate", _("Sertifikat")
        COURSE_ENROLLMENT = "course_enrollment", _("Kursga yozilish")
        REMINDER = "reminder", _("Eslatma")
        GENERAL = "general", _("Umumiy")
        ESSAY_GRADED = "essay_graded", _("Esse baholandi")
        ESSAY_REVIEW_REQUEST = "essay_review_request", _("Esse tekshirish so'rovi")
        ATTENDANCE = "attendance", _("Davomat")
        ATTENDANCE_SUMMARY = "attendance_summary", _("Davomat (guruh xulosasi)")
        OBSERVATION = "observation", _("Sinf kuzatuvi")
        ASSIGNMENT_OVERDUE = "assignment_overdue", _("Topshiriq muddati o'tdi")

    # -- Core -----------------------------------------------------------------
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("qabul qiluvchi"),
    )
    channel = models.CharField(
        _("kanal"),
        max_length=20,
        choices=Channel.choices,
        default=Channel.TELEGRAM,
    )
    notification_type = models.CharField(
        _("xabar turi"),
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
    )

    # -- Content --------------------------------------------------------------
    title = models.CharField(_("sarlavha"), max_length=255)
    message = models.TextField(_("xabar matni"))

    # -- Delivery tracking ----------------------------------------------------
    status = models.CharField(
        _("holat"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    external_id = models.CharField(
        _("tashqi ID"),
        max_length=100,
        blank=True,
        help_text=_("Telegram message_id yoki email Message-ID."),
    )
    error_message = models.TextField(
        _("xatolik xabari"),
        blank=True,
    )

    # -- Related objects (polymorphic pointer) ---------------------------------
    related_test_attempt = models.ForeignKey(
        "tests.TestAttempt",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name=_("bog'langan test urinishi"),
    )
    related_certificate = models.ForeignKey(
        "results.Certificate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name=_("bog'langan sertifikat"),
    )
    related_essay_submission = models.ForeignKey(
        "essays.EssaySubmission",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name=_("bog'langan esse topshirish"),
        help_text=_("Essay notification idempotency kaliti sifatida ishlatiladi."),
    )

    #: Deterministic key that makes delivery idempotent. Telegram webhooks and
    #: Celery retries can fire the same event more than once, so a non-empty
    #: key is UNIQUE: the second attempt is rejected instead of sending a
    #: duplicate message to a parent or a group.
    dedup_key = models.CharField(
        _("idempotentlik kaliti"),
        max_length=200,
        blank=True,
        default="",
    )

    # -- Timestamps -----------------------------------------------------------
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    sent_at = models.DateTimeField(_("yuborilgan"), null=True, blank=True)

    class Meta:
        verbose_name = _("Bildirishnoma")
        verbose_name_plural = _("Bildirishnomalar")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient"], name="idx_notif_recipient"),
            models.Index(fields=["status"], name="idx_notif_status"),
            models.Index(fields=["channel", "status"], name="idx_notif_chan_stat"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["dedup_key"],
                condition=~models.Q(dedup_key=""),
                name="uniq_notification_dedup_key",
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.get_channel_display()}] → {self.recipient}: {self.title}"


# ---------------------------------------------------------------------------
# PushSubscription (Web Push)
# ---------------------------------------------------------------------------
class PushSubscription(models.Model):
    """
    Web Push subscription — brauzer push notification uchun.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        verbose_name=_("foydalanuvchi"),
    )
    endpoint = models.URLField(_("endpoint"), max_length=500)
    p256dh = models.CharField(_("p256dh key"), max_length=255)
    auth = models.CharField(_("auth key"), max_length=255)
    user_agent = models.CharField(_("user agent"), max_length=500, blank=True)
    is_active = models.BooleanField(_("faolmi"), default=True)

    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    last_used_at = models.DateTimeField(_("oxirgi ishlatilgan"), null=True, blank=True)

    class Meta:
        verbose_name = _("Push obuna")
        verbose_name_plural = _("Push obunalar")
        unique_together = ("user", "endpoint")
        indexes = [
            models.Index(fields=["user", "is_active"], name="idx_push_user_active"),
        ]

    def __str__(self) -> str:
        return f"Push: {self.user} ({self.endpoint[:50]}...)"


# ---------------------------------------------------------------------------
# Telegram Auth Token (for web login via Telegram bot)
# ---------------------------------------------------------------------------
class TelegramAuthToken(models.Model):
    """
    Vaqtinchalik token — foydalanuvchi veb-saytdan Telegram orqali kirganda
    ishlatiladi.

    Flow:
        1. User clicks 'Telegram orqali kirish' on login page
        2. Unique token yaratiladi, user redirected to bot: t.me/bot?start=auth_<token>
        3. Bot handler token'ni tekshiradi, Telegram user'ni Django account'ga bog'laydi
        4. Website polls /api/telegram/auth/<token>/ status — 'verified' bo'lsa, login qiladi
    """

    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="URL-safe random token",
    )
    short_code = models.CharField(
        max_length=8,
        default="",
        db_index=True,
        blank=True,
        help_text="6 xonali kod — foydalanuvchi botdan olib saytga kiritadi",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram_auth_tokens",
        null=True,
        blank=True,
        help_text="Foydalanuvchi (token verified bo'lgandan keyin)",
    )
    telegram_chat_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Telegram foydalanuvchi ID (bot orqali tekshirilgandan keyin)",
    )
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Telegram auth token"
        verbose_name_plural = "Telegram auth tokens"
        ordering = ["-created_at"]
        constraints = [
            # Short codes are lookup keys for unconsumed tokens. Empty codes
            # (initial/consumed) may repeat; non-empty active codes must not.
            models.UniqueConstraint(
                fields=["short_code"],
                condition=models.Q(consumed_at__isnull=True) & ~models.Q(short_code=""),
                name="uniq_tgauth_short_code_active",
            ),
        ]

    # Conversation state for collecting user info
    CONVERSATION_STATES = (
        ("idle", "Idle"),
        ("awaiting_name", "Awaiting full name"),
        ("awaiting_phone", "Awaiting phone number"),
        ("code_displayed", "Code displayed to user"),
    )
    conversation_state = models.CharField(
        max_length=20,
        default="idle",
        help_text="Bot suhbat holati — ism/telefon to'plash",
    )
    full_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Foydalanuvchi to'liq ismi (bot orqali kiritilgan)",
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Telefon raqami (bot orqali kiritilgan)",
    )
    phone_verified = models.BooleanField(
        default=False,
        help_text="True if phone was shared via Telegram contact (verified)",
    )

    def __str__(self) -> str:
        status = "verified" if self.is_verified else "pending"
        return f"TGAuth({self.short_code or self.token[:8]}... {status})"

    @property
    def is_expired(self) -> bool:
        from django.utils import timezone

        return timezone.now() > self.created_at + TELEGRAM_AUTH_TOKEN_TTL

    def generate_short_code(self) -> str:
        """Generate a unique 6-digit code (bounded retry, DB is authority)."""
        import secrets

        from django.db import IntegrityError, transaction

        for _ in range(10):
            code = f"{secrets.randbelow(1_000_000):06d}"
            if TelegramAuthToken.objects.filter(
                short_code=code, consumed_at__isnull=True
            ).exists():
                continue
            self.short_code = code
            # If attached to an existing row, persist atomically; collision
            # retry is handled by the caller/unique constraint.
            if self.pk:
                try:
                    with transaction.atomic():
                        self.save(update_fields=["short_code"])
                    return code
                except IntegrityError:
                    continue
            return code
        raise RuntimeError("Could not generate a unique short code after retries.")



# ---------------------------------------------------------------------------
# UserFeedback
# ---------------------------------------------------------------------------
class UserFeedback(models.Model):
    """
    Foydalanuvchilardan kelgan fikr-mulohazalar, takliflar va xatolik xabarlari.
    """

    class Category(models.TextChoices):
        FEEDBACK = "feedback", _("Fikr-mulohaza")
        SUGGESTION = "suggestion", _("Taklif")
        BUG = "bug", _("Xatolik/Muammo")
        PRAISE = "praise", _("Tashakkur")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedbacks",
        verbose_name=_("foydalanuvchi"),
    )
    user_name = models.CharField(_("ism"), max_length=150, blank=True, default="")
    user_phone = models.CharField(_("telefon"), max_length=32, blank=True, default="")
    rating = models.PositiveSmallIntegerField(_("baho"), default=5)
    category = models.CharField(
        _("kategoriya"),
        max_length=20,
        choices=Category.choices,
        default=Category.FEEDBACK,
    )
    message = models.TextField(_("xabar"))
    created_at = models.DateTimeField(_("yaratilgan vaqti"), auto_now_add=True)

    class Meta:
        verbose_name = _("foydalanuvchi fikri")
        verbose_name_plural = _("foydalanuvchilar fikrlari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        author = self.user_name or (self.user and getattr(self.user, "username", "")) or "Anonim"
        return f"Feedback #{self.pk} by {author} ({self.rating}/5)"
