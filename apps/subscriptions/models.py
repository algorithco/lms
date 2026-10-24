"""
Subscriptions app — PaymentReceipt & FraudLog models.
Handles validated payment receipts, Vision AI OCR verification, and Anti-Fraud logging.
"""

from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class PaymentReceipt(models.Model):
    """
    To'lov cheki modeli — Vision OCR tekshiruvi va qat'iy Anti-Fraud filtrlari bilan.
    """

    class PlanType(models.TextChoices):
        STARTER = "starter", _("Starter")
        PRO = "pro", _("Pro")
        PREMIUM = "premium", _("Premium")

    class PaymentSystem(models.TextChoices):
        CLICK = "click", _("Click")
        PAYME = "payme", _("Payme")
        UZUM = "uzum", _("Uzum")
        BANK_CARD = "bank_card", _("Bank kartasi")
        UNKNOWN = "unknown", _("Noma'lum")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verified_payment_receipts",
        verbose_name=_("foydalanuvchi"),
    )
    plan_type = models.CharField(
        _("tarif turi"),
        max_length=20,
        choices=PlanType.choices,
        db_index=True,
    )
    amount = models.DecimalField(
        _("summa"),
        max_digits=12,
        decimal_places=2,
    )
    payment_system = models.CharField(
        _("to'lov tizimi"),
        max_length=20,
        choices=PaymentSystem.choices,
        default=PaymentSystem.UNKNOWN,
        db_index=True,
    )
    transaction_id = models.CharField(
        _("tranzaksiya ID"),
        max_length=128,
        unique=True,
        db_index=True,
    )
    receipt_image = models.ImageField(
        _("chek rasmi"),
        upload_to="receipts/%Y/%m/",
    )
    receipt_hash = models.CharField(
        _("rasm xeshi (SHA-256)"),
        max_length=64,
        db_index=True,
    )
    is_verified = models.BooleanField(
        _("tasdiqlangan"),
        default=False,
        db_index=True,
    )
    admin_note = models.TextField(
        _("admin izohi"),
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(
        _("yaratilgan"),
        auto_now_add=True,
    )

    class Meta:
        verbose_name = _("To'lov cheki")
        verbose_name_plural = _("To'lov cheklari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} — {self.plan_type} ({int(self.amount):,} so'm) — TX:{self.transaction_id}"


class FraudLog(models.Model):
    """
    Firibgarlik jurnali — qalbaki cheklar, o'g'irlangan yoki takroriy tranzaksiya ID lar tarixi.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fraud_logs",
        verbose_name=_("foydalanuvchi"),
    )
    receipt_hash = models.CharField(
        _("rasm xeshi"),
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )
    transaction_id = models.CharField(
        _("tranzaksiya ID"),
        max_length=128,
        blank=True,
        default="",
        db_index=True,
    )
    reason = models.TextField(
        _("firibgarlik sababi"),
    )
    strike_count = models.PositiveIntegerField(
        _("strike soni"),
        default=1,
    )
    banned = models.BooleanField(
        _("bloklandimi"),
        default=False,
    )
    metadata = models.JSONField(
        _("qo'shimcha ma'lumotlar"),
        default=dict,
        blank=True,
    )
    created_at = models.DateTimeField(
        _("aniqlangan vaqt"),
        auto_now_add=True,
    )

    class Meta:
        verbose_name = _("Firibgarlik jurnali")
        verbose_name_plural = _("Firibgarlik jurnallari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} — {self.reason} (banned={self.banned})"
