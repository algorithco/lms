"""
Payments app — Subscription & Payment models.

Subscription Tiers:
    FREE     — Bepul obuna (cheklangan imkoniyatlar)
    PREMIUM  — Premium obuna (to'liq imkoniyatlar)
    FAMILY   — Oila obunasi (3 ta hisob)

Grandec commercial plans (canonical codes):
    START             — 15 000 UZS / 30 kun, haftalik rasmli + matnli esse
                        limitingi va matnli esse sovutish (cooldown) intervali
    PRO               — 60 000 UZS / 30 kun, cheklanmagan esse va testlar
    TEACHER_SPONSORED — 0 UZS, faqat administrator tasdiqlagan ustoz
                        guruhi o'quvchilariga beriladi (sotilmaydi)

Payment Systems (O'zbekiston):
    CLICK    — Click.uz
    PAYME    — Payme.uz
    UZCARD   — UzCard
    STRIPE   — Xalqaro to'lov
    STARS    — Telegram Stars (XTR) — raqamli tovarlar uchun
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SubscriptionPlan(models.Model):
    """
    Obuna rejalari — Free, Premium, Family.
    """

    class PlanType(models.TextChoices):
        FREE = "free", _("Bepul")
        START = "start", _("START")
        STARTER = "starter", _("Starter")
        PRO = "pro", _("Pro")
        PREMIUM = "premium", _("Premium")
        FAMILY = "family", _("Oila")
        #: Not purchasable. Granted by an administrator to eligible students
        #: of an approved teacher group.
        TEACHER_SPONSORED = "teacher_sponsored", _("Ustoz guruhi (homiylik)")

    name = models.CharField(_("nomi"), max_length=100)
    plan_type = models.CharField(
        _("reja turi"),
        max_length=20,
        choices=PlanType.choices,
        unique=True,
    )
    description = models.TextField(_("tavsif"))
    price_monthly = models.DecimalField(
        _("narx (oylik)"),
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    price_yearly = models.DecimalField(
        _("narx (yillik)"),
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    # Features
    max_tests_per_day = models.PositiveIntegerField(
        _("maksimal testlar (kuniga)"),
        default=5,
        help_text=_("0 = cheksiz"),
    )
    max_essays_per_week = models.PositiveIntegerField(
        _("maksimal esselar (haftasiga)"),
        default=2,
        help_text=_("0 = cheksiz"),
    )
    max_ai_grading = models.BooleanField(
        _("AI baholash"), default=True,
    )
    detailed_analytics = models.BooleanField(
        _("batafsil tahlil"), default=False,
    )
    pdf_certificate = models.BooleanField(
        _("PDF sertifikat"), default=False,
    )
    priority_support = models.BooleanField(
        _("ustuvor qo'llab-quvvatlash"), default=False,
    )
    unlimited_tests = models.BooleanField(
        _("cheksiz testlar"), default=False,
    )
    unlimited_essays = models.BooleanField(
        _("cheksiz esselar"), default=False,
    )

    is_active = models.BooleanField(_("faolmi"), default=True)
    sort_order = models.PositiveIntegerField(_("tartib"), default=0)

    # -- Grandec commercial quota configuration ------------------------------
    # Semantics: NULL means "not configured — inherit the platform default",
    # 0 means "explicitly none allowed", a positive number is a hard cap.
    # NULL and 0 are therefore NOT the same value and are never coerced into
    # each other. Use the ``is_unlimited_*`` flags to express "unlimited"
    # rather than encoding it as 0 (which the legacy ``max_*`` fields did).
    image_essay_weekly_limit = models.PositiveIntegerField(
        _("rasmli esse limitingi (haftasiga)"), null=True, blank=True,
        help_text=_("Bo'sh = platforma standarti. 0 = umuman ruxsat yo'q."),
    )
    text_essay_weekly_limit = models.PositiveIntegerField(
        _("matnli esse limitingi (haftasiga)"), null=True, blank=True,
        help_text=_("Bo'sh = platforma standarti. 0 = umuman ruxsat yo'q."),
    )
    text_essay_cooldown_hours = models.PositiveIntegerField(
        _("matnli esse sovutish soati"), null=True, blank=True,
        help_text=_("Bo'sh = platforma standarti. 0 = sovutish yo'q."),
    )
    test_limit = models.PositiveIntegerField(
        _("test limitingi (haftasiga)"), null=True, blank=True,
        help_text=_("Bo'sh = platforma standarti. 0 = umuman ruxsat yo'q."),
    )
    is_unlimited_image_essays = models.BooleanField(
        _("rasmli esse cheksiz"), default=False,
    )
    is_unlimited_text_essays = models.BooleanField(
        _("matnli esse cheksiz"), default=False,
    )
    is_unlimited_tests = models.BooleanField(_("testlar cheksiz"), default=False)
    duration_days = models.PositiveIntegerField(_("davomiylik (kun)"), default=30)
    quota_period_days = models.PositiveIntegerField(
        _("kvota davri (kun)"), default=7,
        help_text=_("Kvota oynasi uzunligi. Standart — 7 kun."),
    )
    telegram_stars_price = models.PositiveIntegerField(
        _("Telegram Stars narxi (XTR)"), null=True, blank=True,
        help_text=_(
            "Telegram ichida yechib olinadigan butun Stars soni. "
            "Bo'sh bo'lsa Telegram orqali sotilmaydi (admin kiritishi shart)."
        ),
    )
    is_public = models.BooleanField(
        _("ommaviy sotuvda"), default=True,
        help_text=_("Belgilanmasa, reja faqat admin orqali beriladi."),
    )

    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Obuna rejası")
        verbose_name_plural = _("Obuna rejaları")
        ordering = ["sort_order", "price_monthly"]

    def __str__(self) -> str:
        return f"{self.name} — ${self.price_monthly}/oy"

    # -- Convenience aliases matching the commercial spec ------------------
    @property
    def code(self) -> str:
        """Canonical plan code (the existing unique ``plan_type`` value)."""
        return self.plan_type

    @property
    def price_uzs(self) -> int:
        """Business reference price in UZS (alias of ``price_monthly``)."""
        return int(Decimal(self.price_monthly or 0))

    @property
    def display_order(self) -> int:
        return self.sort_order

    @property
    def is_purchasable(self) -> bool:
        """Public, active, priced plan that a student may buy."""
        return bool(
            self.is_active
            and self.is_public
            and self.plan_type != self.PlanType.TEACHER_SPONSORED
        )

    @property
    def is_purchasable_in_telegram(self) -> bool:
        return bool(self.is_purchasable and self.telegram_stars_price)

    def quota_snapshot(self) -> dict:
        """Frozen copy of the entitlement-relevant plan configuration."""
        return {
            "plan_type": self.plan_type,
            "image_essay_weekly_limit": self.image_essay_weekly_limit,
            "text_essay_weekly_limit": self.text_essay_weekly_limit,
            "text_essay_cooldown_hours": self.text_essay_cooldown_hours,
            "test_limit": self.test_limit,
            "is_unlimited_image_essays": self.is_unlimited_image_essays,
            "is_unlimited_text_essays": self.is_unlimited_text_essays,
            "is_unlimited_tests": self.is_unlimited_tests,
            "duration_days": self.duration_days,
            "quota_period_days": self.quota_period_days,
            "price_uzs": self.price_uzs,
        }


class UserSubscription(models.Model):
    """
    Foydalanuvchining joriy obunasi.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Faol")
        EXPIRED = "expired", _("Muddati tugagan")
        CANCELLED = "cancelled", _("Bekor qilingan")
        TRIAL = "trial", _("Sinov muddati")
        # Lifecycle states required by the commercial flow. A purchase is only
        # ACTIVE once a verified payment has been recorded — an invoice or a
        # pre-checkout event must never activate access.
        PENDING_PAYMENT = "pending_payment", _("To'lov kutilmoqda")
        PAYMENT_FAILED = "payment_failed", _("To'lov amalga oshmadi")
        REFUNDED = "refunded", _("Qaytarilgan")
        REVOKED = "revoked", _("Bekor qilingan (admin)")

    class Source(models.TextChoices):
        WEBSITE = "website", _("Veb-sayt")
        TELEGRAM_BOT = "telegram_bot", _("Telegram bot")
        ADMIN = "admin", _("Administrator bergan")
        TEACHER_SPONSORED = "teacher_sponsored", _("Ustoz guruhi (homiylik)")
        SPONSORSHIP_DEFAULT = "sponsorship_default", _("Homiylik (standart)")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
        verbose_name=_("foydalanuvchi"),
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        verbose_name=_("reja"),
    )
    status = models.CharField(
        _("holat"),
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    # Dates
    started_at = models.DateTimeField(_("boshlangan"), default=timezone.now)
    expires_at = models.DateTimeField(
        _("tugash vaqti"),
        null=True,
        blank=True,
    )
    cancelled_at = models.DateTimeField(
        _("bekor qilingan"),
        null=True,
        blank=True,
    )

    # Payment
    payment_id = models.CharField(
        _("to'lov ID"),
        max_length=200,
        blank=True,
        help_text=_("To'lov tizimidagi ID"),
    )
    payment_method = models.CharField(
        _("to'lov usuli"),
        max_length=50,
        blank=True,
        choices=[
            ("click", "Click"),
            ("payme", "Payme"),
            ("uzcard", "UzCard"),
            ("stripe", "Stripe"),
            ("card", "Karta (admin tasdiqlagan)"),
            ("stars", "Telegram Stars"),
            ("free", "Bepul"),
        ],
    )

    # -- Provenance & frozen snapshots ---------------------------------------
    # Configuring a plan later must never retroactively rewrite what a student
    # already bought: the purchase snapshots both the plan configuration and
    # the effective entitlement at activation time.
    purchase_source = models.CharField(
        _("sotib olish manbasi"), max_length=30,
        choices=Source.choices, default=Source.WEBSITE, blank=True,
    )
    payment_reference = models.CharField(
        _("to'lov havolasi"), max_length=200, blank=True,
        help_text=_("Masalan: Telegram Stars charge ID."),
    )
    grant_source = models.CharField(
        _("berilish manbasi"), max_length=30, blank=True,
        help_text=_("Admin yoki homiylik orqali berilganda to'ldiriladi."),
    )
    plan_snapshot = models.JSONField(
        _("reja nusxasi"), default=dict, blank=True,
        help_text=_("Sotib olingan paytdagi reja sozlamalari."),
    )
    entitlement_snapshot = models.JSONField(
        _("imkoniyatlar nusxasi"), default=dict, blank=True,
        help_text=_("Sotib olingan paytdagi amaldagi kvotalar."),
    )

    # Trial
    is_trial = models.BooleanField(_("sinov muddatimi"), default=False)
    trial_days = models.PositiveIntegerField(
        _("sinov kunlari"),
        default=7,
    )

    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Foydalanuvchi obunasi")
        verbose_name_plural = _("Foydalanuvchi obunalari")

    def __str__(self) -> str:
        return f"{self.user} — {self.plan.name} ({self.status})"

    @property
    def is_active(self) -> bool:
        """Obuna faolmi?"""
        if self.status != self.Status.ACTIVE:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True

    @property
    def days_remaining(self) -> int:
        """Qolgan kunlar soni."""
        if not self.expires_at:
            return 0
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)

    @property
    def is_admin_granted(self) -> bool:
        return self.purchase_source in {
            self.Source.ADMIN, self.Source.TEACHER_SPONSORED,
            self.Source.SPONSORSHIP_DEFAULT,
        }

    def snapshot_now(self) -> None:
        """Freeze the plan + effective quota configuration onto this row.

        Called at activation time so a later plan edit cannot retroactively
        alter a subscription the student already paid for.
        """
        self.plan_snapshot = self.plan.quota_snapshot() if self.plan_id else {}
        self.entitlement_snapshot = dict(self.plan_snapshot)


# ---------------------------------------------------------------------------
# Usage ledger — atomic, idempotent commercial quota accounting
# ---------------------------------------------------------------------------
class SubscriptionUsage(models.Model):
    """One row per accepted, quota-consuming operation.

    This table — not a counter on the user or a Redis key — is the source of
    truth for commercial quotas. ``idempotency_key`` is UNIQUE, so a retried
    Telegram webhook, a duplicated Celery task or a browser double-submit can
    never charge the same essay twice: the second INSERT raises
    ``IntegrityError``/``get_or_create`` returns the existing row.

    ``period_start`` records which quota window the usage belongs to, so a
    weekly reset needs no destructive cleanup — a new window simply starts
    counting from zero.

    Rows are only ever appended or transitioned between statuses; usage is
    never deleted (they are also the audit trail for support and refunds).
    """

    class Kind(models.TextChoices):
        IMAGE_ESSAY = "image_essay", _("Rasmli esse")
        TEXT_ESSAY = "text_essay", _("Matnli esse")
        TEST = "test", _("Test")

    class Status(models.TextChoices):
        RESERVED = "reserved", _("Zahiralangan")
        COMMITTED = "committed", _("Sarflangan")
        RELEASED = "released", _("Qaytarilgan")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription_usages",
        verbose_name=_("foydalanuvchi"),
    )
    kind = models.CharField(
        _("turi"), max_length=20, choices=Kind.choices,
        db_index=True,
    )
    status = models.CharField(
        _("holat"), max_length=20, choices=Status.choices,
        default=Status.RESERVED, db_index=True,
    )
    idempotency_key = models.CharField(
        _("idempotentlik kaliti"), max_length=160, unique=True,
    )
    period_start = models.DateTimeField(
        _("kvota davri boshlanishi"), db_index=True,
    )
    #: True when this row actually consumes allowance. Administrators can
    #: create explicitly non-counting rows for corrections without deleting
    #: history.
    counts_towards_quota = models.BooleanField(
        _("limitdan hisoblanadi"), default=True,
    )
    plan_type_snapshot = models.CharField(
        _("reja (nusxa)"), max_length=30, blank=True,
    )
    source = models.CharField(_("manba"), max_length=30, blank=True)
    submission = models.ForeignKey(
        "essays.EssaySubmission",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="usage_records",
        verbose_name=_("esse topshirig'i"),
    )
    test_attempt = models.ForeignKey(
        "tests.TestAttempt",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="usage_records",
        verbose_name=_("test urinishi"),
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    committed_at = models.DateTimeField(_("sarflangan vaqt"), null=True, blank=True)
    released_at = models.DateTimeField(_("qaytarilgan vaqt"), null=True, blank=True)
    note = models.CharField(_("izoh"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("Obuna sarfi")
        verbose_name_plural = _("Obuna sarflari")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "kind", "status", "period_start"],
                name="idx_usage_window",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.kind}:{self.status} ({self.idempotency_key})"


# ---------------------------------------------------------------------------
# Per-student administrator override
# ---------------------------------------------------------------------------
class SubscriptionOverride(models.Model):
    """Explicit administrator entitlement override for one student.

    Highest-priority source in the deterministic precedence chain. Every
    quota field is nullable: ``None`` means "inherit from the tier below", so a
    partial override never accidentally disables an entire paid subscription
    (in particular, a NULL must never be read as "zero allowance").
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription_override",
        verbose_name=_("foydalanuvchi"),
    )
    is_active = models.BooleanField(_("faolmi"), default=True)
    image_essay_weekly_limit = models.PositiveIntegerField(null=True, blank=True)
    text_essay_weekly_limit = models.PositiveIntegerField(null=True, blank=True)
    text_essay_cooldown_hours = models.PositiveIntegerField(null=True, blank=True)
    test_limit = models.PositiveIntegerField(null=True, blank=True)
    is_unlimited_image_essays = models.BooleanField(
        null=True, blank=True, default=None,
    )
    is_unlimited_text_essays = models.BooleanField(
        null=True, blank=True, default=None,
    )
    is_unlimited_tests = models.BooleanField(null=True, blank=True, default=None)
    reason = models.TextField(_("sabab"), blank=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="granted_subscription_overrides",
    )
    expires_at = models.DateTimeField(_("tugash vaqti"), null=True, blank=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Admin kvota ustunligi")
        verbose_name_plural = _("Admin kvota ustunliklari")

    def __str__(self) -> str:
        return f"Override: {self.user_id} ({'active' if self.is_active else 'off'})"


# ---------------------------------------------------------------------------
# Teacher-sponsored entitlement
# ---------------------------------------------------------------------------
class TeacherSponsorship(models.Model):
    """Administrator-approved free access for a teacher-group student.

    A teacher creating a group is NOT sufficient: ``approved_at`` must be set
    by a platform administrator before the entitlement becomes effective, so a
    teacher cannot self-grant unlimited free access by adding users to a group.
    Revoking a sponsorship only flips flags — the student's account, essays,
    history and any independently purchased subscription are untouched.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_sponsorships",
    )
    group = models.ForeignKey(
        "courses.StudentGroup",
        on_delete=models.CASCADE,
        related_name="sponsorships",
    )
    is_active = models.BooleanField(_("faolmi"), default=True)
    approved_at = models.DateTimeField(
        _("tasdiqlangan vaqt"), null=True, blank=True,
        help_text=_("Administrator tasdiqlagandan keyin to'ldiriladi."),
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_sponsorships",
    )
    expires_at = models.DateTimeField(_("tugash vaqti"), null=True, blank=True)
    # Nullable per-student overrides on top of the TEACHER_SPONSORED plan.
    image_essay_weekly_limit = models.PositiveIntegerField(null=True, blank=True)
    text_essay_weekly_limit = models.PositiveIntegerField(null=True, blank=True)
    text_essay_cooldown_hours = models.PositiveIntegerField(null=True, blank=True)
    test_limit = models.PositiveIntegerField(null=True, blank=True)
    is_unlimited_image_essays = models.BooleanField(null=True, blank=True, default=None)
    is_unlimited_text_essays = models.BooleanField(null=True, blank=True, default=None)
    is_unlimited_tests = models.BooleanField(null=True, blank=True, default=None)
    note = models.TextField(_("izoh"), blank=True)
    revoked_at = models.DateTimeField(_("bekor qilingan vaqt"), null=True, blank=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Ustoz homiyligi")
        verbose_name_plural = _("Ustoz homiyliklari")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "is_active"], name="idx_sponsor_student"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "group"],
                condition=models.Q(is_active=True),
                name="uniq_active_sponsorship_per_group",
            ),
        ]

    def __str__(self) -> str:
        return f"Sponsor: {self.student_id} via group {self.group_id}"

    @property
    def is_effective(self) -> bool:
        if not self.is_active or self.approved_at is None:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True


# ---------------------------------------------------------------------------
# Entitlement audit log
# ---------------------------------------------------------------------------
class EntitlementAuditLog(models.Model):
    """Append-only log of every entitlement grant / change / revocation."""

    class Action(models.TextChoices):
        GRANT_OVERRIDE = "grant_override", _("Ustunlik berildi")
        UPDATE_OVERRIDE = "update_override", _("Ustunlik o'zgartirildi")
        REVOKE_OVERRIDE = "revoke_override", _("Ustunlik bekor qilindi")
        APPROVE_SPONSORSHIP = "approve_sponsorship", _("Homiylik tasdiqlandi")
        REVOKE_SPONSORSHIP = "revoke_sponsorship", _("Homiylik bekor qilindi")
        ACTIVATE_SUBSCRIPTION = "activate_subscription", _("Obuna faollashtirildi")
        REVOKE_SUBSCRIPTION = "revoke_subscription", _("Obuna bekor qilindi")
        REFUND_SUBSCRIPTION = "refund_subscription", _("Obuna qaytarildi")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="entitlement_actions",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="entitlement_logs",
    )
    action = models.CharField(_("amal"), max_length=32, choices=Action.choices)
    details = models.JSONField(_("tafsilotlar"), default=dict, blank=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Homiylik tarixi")
        verbose_name_plural = _("Homiylik tarixlari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} → {self.student_id}"


# ---------------------------------------------------------------------------
# Telegram Stars orders
# ---------------------------------------------------------------------------
class TelegramOrder(models.Model):
    """A Telegram Stars (XTR) purchase attempt for one plan.

    Access is only activated from a verified ``successful_payment`` update that
    matches this order's opaque ``payload`` and the charged amount — never from
    the invoice or pre-checkout stage, and never from a flag supplied by a
    client. ``telegram_payment_charge_id`` is UNIQUE so Telegram's at-least-once
    update delivery cannot activate a subscription twice.
    """

    class Status(models.TextChoices):
        CREATED = "created", _("Yaratilgan")
        INVOICE_SENT = "invoice_sent", _("Hisob-faktura yuborilgan")
        PAID = "paid", _("To'langan")
        FAILED = "failed", _("Muvaffaqiyatsiz")
        CANCELLED = "cancelled", _("Bekor qilingan")
        REFUNDED = "refunded", _("Qaytarilgan")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram_orders",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="telegram_orders",
    )
    payload = models.CharField(_("payload"), max_length=64, unique=True)
    amount_stars = models.PositiveIntegerField(_("Stars miqdori"))
    currency = models.CharField(_("valyuta"), max_length=8, default="XTR")
    status = models.CharField(
        _("holat"), max_length=20, choices=Status.choices,
        default=Status.CREATED, db_index=True,
    )
    telegram_payment_charge_id = models.CharField(
        _("Telegram to'lov ID"), max_length=200, unique=True,
        null=True, blank=True,
    )
    provider_payment_charge_id = models.CharField(
        _("provayder to'lov ID"), max_length=200, blank=True,
    )
    raw_payload = models.JSONField(_("xom ma'lumot"), default=dict, blank=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)
    paid_at = models.DateTimeField(_("to'langan vaqt"), null=True, blank=True)

    class Meta:
        verbose_name = _("Telegram buyurtma")
        verbose_name_plural = _("Telegram buyurtmalar")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"TG order {self.payload} ({self.status})"


class PaymentHistory(models.Model):
    """
    To'lov tarixi.
    """

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", _("Kutilmoqda")
        COMPLETED = "completed", _("Tugallangan")
        FAILED = "failed", _("Xatolik")
        REFUNDED = "refunded", _("Qaytarilgan")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("foydalanuvchi"),
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        verbose_name=_("reja"),
    )
    amount = models.DecimalField(
        _("summa"),
        max_digits=10,
        decimal_places=2,
    )
    currency = models.CharField(
        _("valyuta"),
        max_length=3,
        default="UZS",
    )
    payment_method = models.CharField(
        _("to'lov usuli"),
        max_length=50,
    )
    payment_id = models.CharField(
        _("to'lov ID"),
        max_length=200,
        blank=True,
    )
    status = models.CharField(
        _("holat"),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    description = models.TextField(_("tavsif"), blank=True)

    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    completed_at = models.DateTimeField(
        _("tugallangan"),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("To'lov tarixi")
        verbose_name_plural = _("To'lov tarixlari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} — {self.amount} {self.currency} ({self.status})"


# ---------------------------------------------------------------------------
# Payment Request (screenshot-based verification)
# ---------------------------------------------------------------------------
class PaymentRequest(models.Model):
    """
    To'lov so'rovi — foydalanuvchi kartaga pul o'tkazadi,
    screenshot'ni botga yuboradi, admin tekshiradi.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Tekshirilmoqda")
        APPROVED = "approved", _("Tasdiqlangan")
        REJECTED = "rejected", _("Rad etilgan")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_requests",
        verbose_name=_("foydalanuvchi"),
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        verbose_name=_("reja"),
    )
    amount = models.DecimalField(
        _("summa"),
        max_digits=10,
        decimal_places=2,
    )
    telegram_message_id = models.BigIntegerField(
        _("Telegram xabar ID"),
        null=True,
        blank=True,
        help_text="Screenshot yuborilgan Telegram xabar ID",
    )
    screenshot_file_id = models.CharField(
        _("screenshot file_id"),
        max_length=255,
        blank=True,
        help_text="Telegram'dan olingan rasm file_id",
    )
    status = models.CharField(
        _("holat"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,  # admin/bot approval queue filters by status frequently
    )
    admin_note = models.TextField(
        _("admin izohi"),
        blank=True,
        help_text="Admin tomonidan qoldirilgan izoh",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_payments",
        verbose_name=_("tekshirgan admin"),
    )
    reviewed_at = models.DateTimeField(
        _("tekshirilgan vaqt"),
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("To'lov so'rovi")
        verbose_name_plural = _("To'lov so'rovlari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} — {self.plan.name} — {self.status}"


# ---------------------------------------------------------------------------
# Payment Receipt (Web & Bot card transfer receipt uploads)
# ---------------------------------------------------------------------------
class PaymentReceipt(models.Model):
    """
    To'lov cheki (karta orqali to'lov).
    Web yoki Telegram bot orqali yuklanadi, admin tasdiqlagach obuna faollashadi.
    """

    class PlanChoice(models.TextChoices):
        STARTER = "starter", _("Starter")
        PREMIUM = "premium", _("Premium")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    class Source(models.TextChoices):
        WEB = "web", _("Web")
        BOT = "bot", _("Bot")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_receipts",
        verbose_name=_("foydalanuvchi"),
    )
    plan = models.CharField(
        _("tarif"),
        max_length=20,
        choices=PlanChoice.choices,
        db_index=True,
    )
    amount = models.DecimalField(
        _("summa"),
        max_digits=12,
        decimal_places=2,
    )
    receipt_image = models.ImageField(
        _("chek rasmi"),
        upload_to="receipts/%Y/%m/",
    )
    image_hash = models.CharField(
        _("rasm xeshi (SHA-256)"),
        max_length=64,
        db_index=True,
        blank=True,
        null=True,
    )
    status = models.CharField(
        _("holat"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    source = models.CharField(
        _("manba"),
        max_length=10,
        choices=Source.choices,
        default=Source.WEB,
        db_index=True,
    )
    admin_note = models.TextField(
        _("admin izohi"),
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("To'lov cheki")
        verbose_name_plural = _("To'lov cheklari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} — {self.plan} ({int(self.amount):,} so'm) — {self.status}"
