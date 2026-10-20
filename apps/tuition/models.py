"""Course tuition billing — a domain *separate from* platform subscriptions.

Grandec has two unrelated financial relationships, and conflating them would be
a correctness bug, not a convenience:

* ``apps.payments`` — the **platform subscription** (START 15 000, PRO 60 000,
  or administrator-granted TEACHER_SPONSORED access). It decides what a student
  may do on the platform.
* this app — **course tuition**, what a student owes their education centre for
  a course or group. A student with free sponsored platform access may still owe
  tuition, and a tuition scholarship never grants platform entitlements.

Nothing in this module reads or writes ``UserSubscription``, ``SubscriptionPlan``
or ``TeacherSponsorship``; that separation is asserted by tests.

Every amount here is *configured* by an administrator. The models ship with no
default price: a policy with no amount invoices nothing, so the platform can
never invent a fee a centre did not set.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.validators import validate_attachment_upload


class PaymentMethod(models.TextChoices):
    """How a tuition payment was recorded.

    Deliberately limited to things an operator can actually verify offline;
    there is no "provider" value, because no payment provider is integrated for
    tuition yet and inventing one would fake a confirmation.
    """

    CASH = "cash", _("Naqd")
    CARD = "card", _("Karta (o'tkazma)")
    BANK = "bank", _("Bank o'tkazmasi")
    ONLINE = "online", _("Online to'lov")
    OTHER = "other", _("Boshqa")


class MidMonthPolicy(models.TextChoices):
    """What happens when a student becomes eligible part-way through a period.

    The default is :attr:`SKIP` — bill nothing for the partial month and start
    with the next full period. Charging a full month for a few days is the kind
    of surprise that generates support tickets, and prorating is a commercial
    decision an administrator must make explicitly.
    """

    SKIP = "skip", _("Qisman davr uchun hisoblanmaydi")
    FULL = "full", _("To'liq davr summasi")
    PRORATED = "prorated", _("Kunlar bo'yicha mutanosib")


class CourseBillingPolicy(models.Model):
    """Administrator-configured tuition for a course and/or a group.

    Specificity is resolved in :func:`apps.tuition.services.resolve_policy`: a
    group-scoped policy beats a course-scoped one for students of that group.
    `due_day` is clamped to the last day of the month, so a policy with
    ``due_day=31`` produces 28/29/30 February instead of rolling into March.
    """

    class Frequency(models.TextChoices):
        MONTHLY = "monthly", _("Oylik")
        QUARTERLY = "quarterly", _("Choraklik")
        ANNUAL = "annual", _("Yillik")
        ONE_TIME = "one_time", _("Bir martalik")

    name = models.CharField(_("nomi"), max_length=150)
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="billing_policies",
        verbose_name=_("kurs"),
    )
    group = models.ForeignKey(
        "courses.StudentGroup",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="billing_policies",
        verbose_name=_("guruh"),
    )
    amount_uzs = models.PositiveIntegerField(
        _("summa (so'm)"),
        default=0,
        help_text=_("0 — narx belgilanmagan; bu holda hisob-faktura yaratilmaydi."),
    )
    billing_frequency = models.CharField(
        _("davriylik"),
        max_length=12,
        choices=Frequency.choices,
        default=Frequency.MONTHLY,
    )
    due_day = models.PositiveSmallIntegerField(
        _("to'lov kuni"),
        default=10,
        help_text=_("1–31. Oyning kunlari yetmasa, oxirgi kun olinadi."),
    )
    grace_days = models.PositiveSmallIntegerField(_("imtiyozli kunlar"), default=0)
    mid_month_policy = models.CharField(
        _("oy o'rtasida qo'shilish"),
        max_length=12,
        choices=MidMonthPolicy.choices,
        default=MidMonthPolicy.SKIP,
    )
    installment_allowed = models.BooleanField(_("bo'lib to'lash mumkin"), default=False)
    installments = models.PositiveSmallIntegerField(_("bo'lib to'lash soni"), default=1)
    effective_from = models.DateField(
        _("kuchga kirgan sana"), default=timezone.localdate
    )
    effective_until = models.DateField(_("amal qilish tugashi"), null=True, blank=True)
    payment_instructions = models.TextField(
        _("to'lov bo'yicha ko'rsatma"),
        blank=True,
        help_text=_(
            "Masalan: karta raqami va to'lov izohi. Public guruhga yuborilmaydi."
        ),
    )
    accepted_methods = models.JSONField(
        _("qabul qilinadigan usullar"),
        default=list,
        blank=True,
    )
    #: ``{"before": [3], "due": [0], "overdue": [3, 7, 14],
    #: "quiet_start": 21, "quiet_end": 8}`` — day offsets relative to the due
    #: date. An empty policy means "no automatic reminders".
    reminder_policy = models.JSONField(_("eslatma siyosati"), default=dict, blank=True)
    is_active = models.BooleanField(_("faol"), default=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Kurs to'lov siyosati")
        verbose_name_plural = _("Kurs to'lov siyosatlari")
        ordering = ["-effective_from", "name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(course__isnull=False)
                | models.Q(group__isnull=False),
                name="tuition_policy_needs_course_or_group",
            ),
        ]

    def __str__(self) -> str:
        scope = (
            self.group.name
            if self.group_id
            else (self.course.title if self.course_id else "—")
        )
        return f"{self.name} ({scope}) — {self.amount_uzs} so'm"

    def clean(self) -> None:
        errors = {}
        if not (1 <= int(self.due_day) <= 31):
            errors["due_day"] = _("To'lov kuni 1 va 31 orasida bo'lishi kerak.")
        if self.effective_until and self.effective_until < self.effective_from:
            errors["effective_until"] = _(
                "Tugash sanasi boshlanish sanasidan keyin bo'lishi kerak."
            )
        if self.installments < 1:
            errors["installments"] = _("Bo'lib to'lash soni kamida 1.")
        if errors:
            raise ValidationError(errors)

    def is_effective_on(self, on_date: date) -> bool:
        if not self.is_active:
            return False
        if self.effective_from and on_date < self.effective_from:
            return False
        return not (self.effective_until and on_date > self.effective_until)

    def due_date_for(self, year: int, month: int) -> date:
        """Due date inside *year*/*month*, clamped to the month's last day.

        This is the documented month-end policy: ``due_day=31`` in February
        gives the 28th (or 29th), never the 3rd of March.
        """
        last_day = monthrange(year, month)[1]
        return date(year, month, min(int(self.due_day), last_day))

    def reminder_offsets(self) -> dict:
        policy = self.reminder_policy or {}
        return {
            "before": [int(offset) for offset in policy.get("before", [])],
            "due": [int(offset) for offset in policy.get("due", [])],
            "overdue": [int(offset) for offset in policy.get("overdue", [])],
            "quiet_start": int(policy.get("quiet_start", 21)),
            "quiet_end": int(policy.get("quiet_end", 8)),
        }

    def scope_key(self) -> str:
        """Stable invoice-uniqueness key (NULL-safe by construction)."""
        if self.group_id:
            return f"group:{self.group_id}"
        if self.course_id:
            return f"course:{self.course_id}"
        return f"policy:{self.pk}"


class StudentTuitionAgreement(models.Model):
    """A per-student negotiated price, discount, scholarship or exemption."""

    class DiscountKind(models.TextChoices):
        NONE = "none", _("Yo'q")
        PERCENT = "percent", _("Foiz chegirma")
        AMOUNT = "amount", _("Summa chegirma")
        FULL_WAIVER = "full_waiver", _("To'liq ozod (stipendiya)")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Faol")
        SUSPENDED = "suspended", _("To'xtatilgan")
        ENDED = "ended", _("Tugagan")

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tuition_agreements",
        verbose_name=_("o'quvchi"),
    )
    enrollment = models.ForeignKey(
        "courses.Enrollment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tuition_agreements",
        verbose_name=_("yozilish"),
    )
    billing_policy = models.ForeignKey(
        CourseBillingPolicy,
        on_delete=models.CASCADE,
        related_name="agreements",
        verbose_name=_("to'lov siyosati"),
    )
    negotiated_amount_uzs = models.PositiveIntegerField(
        _("kelishilgan summa"),
        null=True,
        blank=True,
        help_text=_("Bo'sh bo'lsa — siyosatdagi summa ishlatiladi."),
    )
    discount_kind = models.CharField(
        _("chegirma turi"),
        max_length=16,
        choices=DiscountKind.choices,
        default=DiscountKind.NONE,
    )
    discount_percent = models.DecimalField(
        _("chegirma foizi"),
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    discount_amount_uzs = models.PositiveIntegerField(_("chegirma summasi"), default=0)
    scholarship_note = models.CharField(
        _("stipendiya izohi"),
        max_length=200,
        blank=True,
    )
    effective_from = models.DateField(_("kuchga kirgan"), default=timezone.localdate)
    effective_until = models.DateField(_("tugashi"), null=True, blank=True)
    status = models.CharField(
        _("holat"),
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tuition_agreements_created",
        verbose_name=_("yaratgan"),
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("O'quvchi to'lov shartnomasi")
        verbose_name_plural = _("O'quvchi to'lov shartnomalari")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "billing_policy"],
                condition=models.Q(status="active"),
                name="uniq_active_tuition_agreement",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} · {self.billing_policy_id} · {self.discount_kind}"

    def clean(self) -> None:
        if self.discount_kind == self.DiscountKind.PERCENT:
            if not (0 <= float(self.discount_percent) <= 100):
                raise ValidationError(
                    {
                        "discount_percent": _(
                            "Chegirma foizi 0 va 100 orasida bo'lishi kerak."
                        )
                    }
                )

    def is_effective_on(self, on_date: date) -> bool:
        if self.status != self.Status.ACTIVE:
            return False
        if self.effective_from and on_date < self.effective_from:
            return False
        return not (self.effective_until and on_date > self.effective_until)

    def net_amount(self, base_amount: int) -> int:
        """Apply waiver/discount to *base_amount*. Never below zero.

        A full waiver is an *exemption*: the invoice is still created (so the
        student appears in reporting) but with a zero amount due.
        """
        if self.discount_kind == self.DiscountKind.FULL_WAIVER:
            return 0
        amount = int(base_amount)
        if self.discount_kind == self.DiscountKind.PERCENT:
            amount -= round(amount * float(self.discount_percent) / 100)
        elif self.discount_kind == self.DiscountKind.AMOUNT:
            amount -= int(self.discount_amount_uzs)
        return max(0, amount)


class CourseInvoice(models.Model):
    """One billing period for one student. Amounts are snapshot at creation."""

    class Status(models.TextChoices):
        UNPAID = "unpaid", _("To'lanmagan")
        PARTIALLY_PAID = "partially_paid", _("Qisman to'langan")
        PENDING_VERIFICATION = "pending_verification", _("Tekshirilmoqda")
        PAID = "paid", _("To'langan")
        OVERDUE = "overdue", _("Muddati o'tgan")
        WAIVED = "waived", _("To'lashdan ozod")
        CANCELLED = "cancelled", _("Bekor qilingan")
        REFUNDED = "refunded", _("Qaytarilgan")
        ADJUSTED = "adjusted", _("Tuzatilgan")

    STATUS_LABELS = {
        "unpaid": "To'lanmagan",
        "partially_paid": "Qisman to'langan",
        "pending_verification": "Tekshirilmoqda",
        "paid": "To'langan",
        "overdue": "Muddati o'tgan",
        "waived": "To'lashdan ozod",
        "cancelled": "Bekor qilingan",
        "refunded": "Qaytarilgan",
        "adjusted": "Tuzatilgan",
    }

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_invoices",
        verbose_name=_("o'quvchi"),
    )
    policy = models.ForeignKey(
        CourseBillingPolicy,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name=_("siyosat"),
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tuition_invoices",
        verbose_name=_("kurs"),
    )
    enrollment = models.ForeignKey(
        "courses.Enrollment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tuition_invoices",
        verbose_name=_("yozilish"),
    )
    agreement = models.ForeignKey(
        StudentTuitionAgreement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name=_("shartnoma"),
    )
    scope_key = models.CharField(
        _("qamrov kaliti"),
        max_length=64,
        help_text=_("Takroriy hisob-fakturani oldini oluvchi deterministik kalit."),
    )
    billing_period_start = models.DateField(_("davr boshlanishi"), db_index=True)
    billing_period_end = models.DateField(_("davr tugashi"))
    period_label = models.CharField(_("davr"), max_length=32, blank=True)
    base_amount_uzs = models.DecimalField(
        _("asosiy summa"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    discount_amount_uzs = models.DecimalField(
        _("chegirma"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    amount_due_uzs = models.DecimalField(
        _("to'lanadigan summa"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    paid_amount_uzs = models.DecimalField(
        _("tasdiqlangan to'lov"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    pending_amount_uzs = models.DecimalField(
        _("tekshirilayotgan to'lov"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    discount_kind = models.CharField(
        _("chegirma turi"),
        max_length=16,
        blank=True,
        default="",
    )
    is_installment = models.BooleanField(_("bo'lib to'lash"), default=False)
    installment_number = models.PositiveSmallIntegerField(
        _("bo'lib to'lash raqami"), default=1
    )
    due_date = models.DateField(_("to'lov muddati"), db_index=True)
    grace_until = models.DateField(_("imtiyoz tugashi"), null=True, blank=True)
    status = models.CharField(
        _("holat"),
        max_length=24,
        choices=Status.choices,
        default=Status.UNPAID,
        db_index=True,
    )
    note = models.CharField(_("izoh"), max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tuition_invoices_created",
        verbose_name=_("yaratgan"),
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Kurs hisob-fakturasi")
        verbose_name_plural = _("Kurs hisob-fakturalari")
        ordering = ["-billing_period_start", "student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "billing_period_start", "scope_key"],
                name="uniq_tuition_invoice_period",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "due_date"], name="idx_tuition_inv_status"),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} · {self.period_label or self.billing_period_start} · {self.status}"

    @property
    def balance_uzs(self):
        """Confirmed outstanding balance (never negative)."""
        return max(0, self.amount_due_uzs - self.paid_amount_uzs)

    @property
    def status_label(self) -> str:
        return self.STATUS_LABELS.get(self.status, self.status)

    @property
    def is_open(self) -> bool:
        return self.status not in {
            self.Status.PAID,
            self.Status.WAIVED,
            self.Status.CANCELLED,
        }

    @property
    def awaiting_confirmation(self) -> bool:
        """A submitted payment covers the balance but is not confirmed yet."""
        return (
            self.status == self.Status.PENDING_VERIFICATION
            and self.pending_amount_uzs >= self.balance_uzs
        )


class CoursePayment(models.Model):
    """A tuition payment. It is *not* money until an authorized human confirms it."""

    class Status(models.TextChoices):
        PENDING_VERIFICATION = "pending_verification", _("Tekshirilmoqda")
        VERIFIED = "verified", _("Tasdiqlangan")
        REJECTED = "rejected", _("Rad etilgan")
        REFUNDED = "refunded", _("Qaytarilgan")

    invoice = models.ForeignKey(
        CourseInvoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name=_("hisob-faktura"),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_payments",
        verbose_name=_("o'quvchi"),
    )
    amount_uzs = models.DecimalField(
        _("summa"),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    method = models.CharField(
        _("usul"),
        max_length=12,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CARD,
    )
    reference = models.CharField(
        _("to'lov havolasi/raqami"),
        max_length=120,
        blank=True,
        default="",
    )
    proof = models.FileField(
        _("to'lov dalili"),
        upload_to="tuition/proofs/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_attachment_upload],
    )
    note = models.TextField(_("izoh"), blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tuition_payments_submitted",
        verbose_name=_("topshirgan"),
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tuition_payments_verified",
        verbose_name=_("tasdiqlagan"),
    )
    verified_at = models.DateTimeField(_("tasdiqlangan vaqt"), null=True, blank=True)
    status = models.CharField(
        _("holat"),
        max_length=24,
        choices=Status.choices,
        default=Status.PENDING_VERIFICATION,
        db_index=True,
    )
    rejection_reason = models.CharField(
        _("rad etish sababi"), max_length=200, blank=True
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Kurs to'lovi")
        verbose_name_plural = _("Kurs to'lovlari")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                # The same bank reference must not be recorded twice — that is
                # how a single transfer becomes two receipts.
                fields=["method", "reference"],
                condition=~models.Q(reference=""),
                name="uniq_tuition_payment_reference",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} · {self.amount_uzs} · {self.status}"

    @property
    def is_confirmed(self) -> bool:
        return self.status == self.Status.VERIFIED


class PaymentReminderLog(models.Model):
    """Idempotent record of one reminder. One row per (invoice, stage, recipient)."""

    class Stage(models.TextChoices):
        BEFORE_DUE = "before_due", _("Muddatdan oldin")
        DUE_TODAY = "due_today", _("Muddat kuni")
        OVERDUE = "overdue", _("Muddati o'tgan")
        AWAITING_CONFIRMATION = "awaiting_confirmation", _("Tasdiq kutilmoqda")

    class Channel(models.TextChoices):
        TELEGRAM = "telegram", _("Telegram")
        DASHBOARD = "dashboard", _("Veb-panel")

    class Status(models.TextChoices):
        PENDING = "pending", _("Kutilmoqda")
        SENT = "sent", _("Yuborildi")
        FAILED = "failed", _("Xatolik")
        SKIPPED = "skipped", _("O'tkazib yuborildi")

    invoice = models.ForeignKey(
        CourseInvoice,
        on_delete=models.CASCADE,
        related_name="reminders",
        verbose_name=_("hisob-faktura"),
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tuition_reminders",
        verbose_name=_("qabul qiluvchi"),
    )
    stage = models.CharField(_("bosqich"), max_length=24, choices=Stage.choices)
    channel = models.CharField(
        _("kanal"),
        max_length=16,
        choices=Channel.choices,
        default=Channel.TELEGRAM,
    )
    idempotency_key = models.CharField(
        _("idempotentlik kaliti"), max_length=200, unique=True
    )
    status = models.CharField(
        _("holat"),
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    error = models.TextField(_("xatolik"), blank=True)
    sent_at = models.DateTimeField(_("yuborilgan"), null=True, blank=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("To'lov eslatmasi")
        verbose_name_plural = _("To'lov eslatmalari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.invoice_id} · {self.stage} · {self.status}"


class TuitionAuditLog(models.Model):
    """Append-only trail for every money-touching change.

    Corrections are allowed — mistakes happen — but they are never silent: the
    actor, the field, the previous value and the new value are all recorded.
    """

    class Action(models.TextChoices):
        POLICY_CREATED = "policy_created", _("Siyosat yaratildi")
        POLICY_UPDATED = "policy_updated", _("Siyosat o'zgartirildi")
        AGREEMENT_CREATED = "agreement_created", _("Shartnoma yaratildi")
        AGREEMENT_UPDATED = "agreement_updated", _("Shartnoma o'zgartirildi")
        INVOICE_CREATED = "invoice_created", _("Hisob-faktura yaratildi")
        INVOICE_UPDATED = "invoice_updated", _("Hisob-faktura o'zgartirildi")
        INVOICE_CANCELLED = "invoice_cancelled", _("Hisob-faktura bekor qilindi")
        INVOICE_ADJUSTED = "invoice_adjusted", _("Hisob-faktura tuzatildi")
        INVOICE_MARKED_OVERDUE = (
            "invoice_marked_overdue",
            _("Muddati o'tgan deb belgilandi"),
        )
        PAYMENT_SUBMITTED = "payment_submitted", _("To'lov topshirildi")
        PAYMENT_VERIFIED = "payment_verified", _("To'lov tasdiqlandi")
        PAYMENT_REJECTED = "payment_rejected", _("To'lov rad etildi")
        PAYMENT_REFUNDED = "payment_refunded", _("To'lov qaytarildi")
        REMINDER_SENT = "reminder_sent", _("Eslatma yuborildi")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tuition_audit_entries",
        verbose_name=_("bajargan"),
    )
    action = models.CharField(
        _("amal"), max_length=32, choices=Action.choices, db_index=True
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tuition_audit_entries_about",
        verbose_name=_("o'quvchi"),
    )
    policy = models.ForeignKey(
        CourseBillingPolicy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    agreement = models.ForeignKey(
        StudentTuitionAgreement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    invoice = models.ForeignKey(
        CourseInvoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    payment = models.ForeignKey(
        CoursePayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    field = models.CharField(_("maydon"), max_length=48, blank=True)
    old_value = models.CharField(max_length=200, blank=True)
    new_value = models.CharField(max_length=200, blank=True)
    reason = models.CharField(_("sabab"), max_length=200, blank=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("To'lov auditi")
        verbose_name_plural = _("To'lov auditlari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} → invoice={self.invoice_id} payment={self.payment_id}"


class StudentTuition(models.Model):
    """
    O'quvchining guruh bo'yicha kurs oylik to'lovi (Tuition Billing).
    """

    class Status(models.TextChoices):
        PAID = "paid", _("To'langan")
        PENDING = "pending", _("Kutilmoqda")
        OVERDUE = "overdue", _("Muddati o'tgan")

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tuition_records",
        verbose_name=_("o'quvchi"),
    )
    group = models.ForeignKey(
        "courses.StudentGroup",
        on_delete=models.CASCADE,
        related_name="tuition_records",
        verbose_name=_("guruh"),
    )
    monthly_fee = models.PositiveIntegerField(
        _("oylik to'lov summasi (so'm)"),
        default=400000,
    )
    due_date = models.DateField(
        _("to'lov muddati"),
        db_index=True,
    )
    status = models.CharField(
        _("to'lov holati"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    paid_at = models.DateTimeField(
        _("to'langan vaqt"),
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("O'quvchi kurs to'lovi")
        verbose_name_plural = _("O'quvchilar kurs to'lovlari")
        ordering = ["-due_date", "student__first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "group", "due_date"],
                name="uniq_student_group_tuition_due",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.student_id} · {self.group_id} · {self.monthly_fee} ({self.status})"
        )

    def mark_paid(self) -> None:
        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at", "updated_at"])
