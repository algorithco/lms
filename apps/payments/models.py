"""
Payments app — Subscription & Payment models.

Subscription Tiers:
    FREE     — Bepul obuna (cheklangan imkoniyatlar)
    PREMIUM  — Premium obuna (to'liq imkoniyatlar)
    FAMILY   — Oila obunasi (3 ta hisob)

Payment Systems (O'zbekiston):
    CLICK    — Click.uz
    PAYME    — Payme.uz
    UZCARD   — UzCard
    STRIPE   — Xalqaro to'lov
"""
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
        STARTER = "starter", _("Starter")
        PRO = "pro", _("Pro")
        PREMIUM = "premium", _("Premium")
        FAMILY = "family", _("Oila")

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

    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Obuna rejası")
        verbose_name_plural = _("Obuna rejaları")
        ordering = ["sort_order", "price_monthly"]

    def __str__(self) -> str:
        return f"{self.name} — ${self.price_monthly}/oy"


class UserSubscription(models.Model):
    """
    Foydalanuvchining joriy obunasi.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Faol")
        EXPIRED = "expired", _("Muddati tugagan")
        CANCELLED = "cancelled", _("Bekor qilingan")
        TRIAL = "trial", _("Sinov muddati")

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
            ("free", "Bepul"),
        ],
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
