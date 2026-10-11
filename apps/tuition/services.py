"""Canonical course-tuition service.

One module owns the money rules, and every surface — Django admin, the REST
API, the Telegram bot, the parent portal and the weekly report — calls it. No
view, handler or admin action recomputes a balance.

Course tuition is separate from platform subscriptions. Invoices use only
administrator-configured amounts, are scoped to eligible enrollments/members,
and claimed payments do not affect balances until an authorized verification.
"""
from __future__ import annotations

import json
import logging
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.courses.models import Course, Enrollment, StudentGroup

from .models import (
    CourseBillingPolicy,
    CourseInvoice,
    CoursePayment,
    MidMonthPolicy,
    PaymentReminderLog,
    StudentTuitionAgreement,
    TuitionAuditLog,
)

PaymentReminderStage = PaymentReminderLog.Stage
logger = logging.getLogger(__name__)
ZERO = Decimal("0.00")
OPEN_STATUSES = (
    CourseInvoice.Status.UNPAID,
    CourseInvoice.Status.PARTIALLY_PAID,
    CourseInvoice.Status.PENDING_VERIFICATION,
    CourseInvoice.Status.OVERDUE,
)


class TuitionError(Exception):
    """A rejected tuition operation."""


def today() -> date:
    return timezone.localdate()


def month_bounds(reference: date) -> tuple[date, date]:
    last = monthrange(reference.year, reference.month)[1]
    return date(reference.year, reference.month, 1), date(reference.year, reference.month, last)


def add_months(reference: date, months: int) -> date:
    month_index = reference.month - 1 + months
    year = reference.year + month_index // 12
    month = month_index % 12 + 1
    day = min(reference.day, monthrange(year, month)[1])
    return date(year, month, day)


def period_label(start: date, end: date) -> str:
    if start.year == end.year and start.month == end.month:
        return f"{start:%Y-%m}"
    return f"{start:%Y-%m-%d} — {end:%Y-%m-%d}"


def billing_period_bounds(policy: CourseBillingPolicy, reference: date) -> tuple[date, date]:
    """Calendar cycle containing a requested date for this configured frequency."""
    frequency = policy.billing_frequency
    if frequency == CourseBillingPolicy.Frequency.ONE_TIME:
        return policy.effective_from, policy.effective_from
    if frequency == CourseBillingPolicy.Frequency.QUARTERLY:
        start_month = ((reference.month - 1) // 3) * 3 + 1
        start = date(reference.year, start_month, 1)
        return start, add_months(start, 3) - timedelta(days=1)
    if frequency == CourseBillingPolicy.Frequency.ANNUAL:
        return date(reference.year, 1, 1), date(reference.year, 12, 31)
    return month_bounds(reference)


def resolve_policy(student, *, on_date: date | None = None,
                   course: Course | None = None,
                   group: StudentGroup | None = None):
    """Most specific effective policy for this student; group scope takes precedence."""
    on_date = on_date or today()
    candidates = CourseBillingPolicy.objects.filter(is_active=True)
    group_ids = list(student.student_groups.values_list("pk", flat=True))
    course_ids = list(
        Enrollment.objects.filter(student=student).values_list("course_id", flat=True)
    )
    scope_filter = Q()
    if group is not None:
        scope_filter |= Q(group=group)
    if course is not None:
        scope_filter |= Q(course=course)
    if not scope_filter:
        scope_filter = Q(group_id__in=group_ids) | Q(course_id__in=course_ids)
    matches = [
        policy for policy in candidates.filter(scope_filter)
        if policy.is_effective_on(on_date)
    ]
    if not matches:
        return None
    matches.sort(key=lambda policy: (
        0 if policy.group_id else 1,
        -policy.effective_from.toordinal(),
        -policy.pk,
    ))
    return matches[0]


def agreement_for(student, policy, *, on_date: date | None = None):
    on_date = on_date or today()
    rows = StudentTuitionAgreement.objects.filter(
        student=student, billing_policy=policy,
        status=StudentTuitionAgreement.Status.ACTIVE,
    ).order_by("-effective_from", "-pk")
    for agreement in rows:
        if agreement.is_effective_on(on_date):
            return agreement
    return None


def effective_amount(policy, agreement) -> dict:
    base = int(agreement.negotiated_amount_uzs) if (
        agreement and agreement.negotiated_amount_uzs is not None
    ) else int(policy.amount_uzs or 0)
    if agreement is None:
        return {
            "base_uzs": base, "discount_uzs": 0, "net_uzs": base,
            "discount_kind": "", "waived": False,
        }
    net = agreement.net_amount(base)
    return {
        "base_uzs": base,
        "discount_uzs": max(0, base - net),
        "net_uzs": net,
        "discount_kind": agreement.discount_kind,
        "waived": agreement.discount_kind == StudentTuitionAgreement.DiscountKind.FULL_WAIVER,
    }


def eligibility_date(student, policy) -> date | None:
    """Best-known persisted date when the student entered this billing scope."""
    policy_data = CourseBillingPolicy.objects.filter(pk=policy.pk).values(
        "group_id", "course_id", "effective_from",
    ).first()
    if policy_data is None:
        return None
    if policy_data["group_id"]:
        group_row = StudentGroup.objects.filter(
            pk=policy_data["group_id"], students__pk=student.pk,
        ).values("created_at", "students__date_joined").first()
        if group_row is None:
            return None
        known = [
            timezone.localtime(value).date()
            for value in (group_row["created_at"], group_row["students__date_joined"])
            if value is not None
        ]
        return max(known) if known else None
    enrolled_at = Enrollment.objects.filter(
        student_id=student.pk, course_id=policy_data["course_id"],
    ).order_by("enrolled_at", "pk").values_list("enrolled_at", flat=True).first()
    return timezone.localtime(enrolled_at).date() if enrolled_at else None


def _is_student(student) -> bool:
    """Check the current persisted account state, not a stale relation cache."""
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(
        pk=student.pk, is_active=True, role="student",
    ).exists()


def prorate_amount(amount: int, *, eligibility: date, period_start: date,
                   period_end: date, policy) -> int:
    """Apply the explicit configured partial-period policy."""
    if amount <= 0 or eligibility <= period_start:
        return amount
    if policy.mid_month_policy == MidMonthPolicy.SKIP:
        return 0
    if policy.mid_month_policy == MidMonthPolicy.FULL:
        return amount
    total_days = (period_end - period_start).days + 1
    remaining = (period_end - eligibility).days + 1
    remaining = max(1, min(total_days, remaining))
    value = Decimal(amount) * Decimal(remaining) / Decimal(total_days)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _fmt(value) -> str:
    """Format audit values deterministically without trusting model reprs."""
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return format(Decimal(str(value)), ".2f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(
                value, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, default=str,
            )
        except (TypeError, ValueError):
            return "[unserializable]"
    if isinstance(value, (str, bool)):
        return str(value)
    return str(value)


def _audit(action: str, *, actor=None, student=None, policy=None, agreement=None,
           invoice=None, payment=None, field: str = "", old_value: str = "",
           new_value: str = "", reason: str = "") -> TuitionAuditLog:
    return TuitionAuditLog.objects.create(
        actor=actor, action=action, student=student, policy=policy,
        agreement=agreement, invoice=invoice, payment=payment, field=field,
        old_value=_fmt(old_value)[:200], new_value=_fmt(new_value)[:200],
        reason=reason[:200],
    )


def ensure_invoice(student, policy, *, period_start: date | None = None,
                   actor=None, reason: str = "", installment: tuple[int, int] | None = None,
                   on_date: date | None = None) -> tuple[CourseInvoice, bool]:
    """Create or retrieve a cycle invoice under the database uniqueness constraint."""
    # Refresh caller-supplied instances so a stale cached policy cannot change
    # eligibility, amounts, effective windows or scope during invoice creation.
    policy = CourseBillingPolicy.objects.get(pk=policy.pk)
    reference = period_start or on_date or today()
    cycle_start, cycle_end = billing_period_bounds(policy, reference)
    on_date = on_date or today()
    if not policy.is_effective_on(on_date):
        raise TuitionError("To'lov siyosati bu sanada faol emas.")
    eligibility = eligibility_date(student, policy)
    if eligibility is None or not _is_student(student):
        raise TuitionError("O'quvchi bu kurs/guruh uchun hisoblanmaydi.")
    if eligibility > cycle_end:
        raise TuitionError("O'quvchi hisob davri tugaganidan keyin qo'shilgan.")

    # The price in force is the one agreed when the invoice is *issued*, not the
    # one in force on the cycle's due date: an administrator who grants a
    # discount or scholarship today must see it on today's invoice, even though
    # this cycle's due date has already passed.
    agreement = agreement_for(student, policy, on_date=today())
    amounts = effective_amount(policy, agreement)
    amount = prorate_amount(
        amounts["net_uzs"], eligibility=eligibility, period_start=cycle_start,
        period_end=cycle_end, policy=policy,
    )
    discount_amount = amounts["base_uzs"] - amount
    if policy.billing_frequency == CourseBillingPolicy.Frequency.ONE_TIME:
        due = policy.due_date_for(cycle_start.year, cycle_start.month)
        if on_date < due or not policy.is_effective_on(due):
            raise TuitionError("Bir martalik hisob-faktura to'lov muddati kelganda yaratiladi.")
    if amount <= 0 and not amounts["waived"]:
        raise TuitionError("Bu davr uchun to'lov hisoblanmaydi.")

    installments = int(policy.installments or 1) if policy.installment_allowed else 1
    index, total = installment or (1, max(1, installments))
    scope = policy.scope_key()
    if total > 1:
        scope = f"{scope}:i{index}of{total}"
    with transaction.atomic():
        # Serialize this student's first invoice in a cycle: until an invoice
        # exists there is no invoice row to lock, but the user row is stable.
        type(student).objects.select_for_update().get(pk=student.pk)
        existing = CourseInvoice.objects.select_for_update().filter(
            student=student, billing_period_start=cycle_start, scope_key=scope,
        ).first()
        if existing is not None:
            return existing, False
        share = amount
        if total > 1:
            per = int(Decimal(amount) / Decimal(total))
            share = per if index < total else amount - per * (total - 1)
        due = policy.due_date_for(cycle_start.year, cycle_start.month)
        if total > 1:
            installment_date = add_months(cycle_start, index - 1)
            due = policy.due_date_for(installment_date.year, installment_date.month)
        if not policy.is_effective_on(due):
            raise TuitionError("To'lov siyosati bu hisob muddatida faol emas.")
        label = period_label(cycle_start, cycle_end)
        if total > 1:
            label = f"{label} ({index}/{total})"
        try:
            invoice = CourseInvoice.objects.create(
                student=student,
                policy=policy,
                course_id=policy.course_id,
                enrollment=Enrollment.objects.filter(
                    student=student, course_id=policy.course_id,
                ).first() if policy.course_id else None,
                agreement=agreement,
                scope_key=scope,
                billing_period_start=cycle_start,
                billing_period_end=cycle_end,
                period_label=label,
                base_amount_uzs=Decimal(amounts["base_uzs"]),
                discount_amount_uzs=Decimal(discount_amount),
                amount_due_uzs=Decimal(share),
                discount_kind=amounts["discount_kind"],
                is_installment=total > 1,
                installment_number=index,
                due_date=due,
                grace_until=due + timedelta(days=int(policy.grace_days or 0)),
                status=(CourseInvoice.Status.WAIVED if share <= 0 else CourseInvoice.Status.UNPAID),
                created_by=actor,
            )
        except IntegrityError:
            return CourseInvoice.objects.get(
                student=student, billing_period_start=cycle_start, scope_key=scope,
            ), False
        _audit(
            TuitionAuditLog.Action.INVOICE_CREATED, actor=actor, student=student,
            policy=policy, invoice=invoice, new_value=str(share), reason=reason,
        )
    return invoice, True


def generate_period_invoices(period_start: date, *, actor=None, dry_run: bool = False,
                             reason: str = "", policy=None) -> dict:
    """Generate eligible invoices due in the requested calendar month, idempotently."""
    requested_start, requested_end = month_bounds(period_start)
    policies = CourseBillingPolicy.objects.filter(is_active=True)
    if policy is not None:
        policies = policies.filter(pk=policy.pk)
    created = skipped = 0
    planned = []
    for billing_policy in policies.select_related("course", "group"):
        frequency = billing_policy.billing_frequency
        if frequency == CourseBillingPolicy.Frequency.MONTHLY:
            if billing_policy.amount_uzs == 0:
                continue
            cycle_start, cycle_end = requested_start, requested_end
        elif frequency == CourseBillingPolicy.Frequency.QUARTERLY:
            if requested_start.month not in (1, 4, 7, 10):
                continue
            cycle_start, cycle_end = billing_period_bounds(billing_policy, requested_start)
        elif frequency == CourseBillingPolicy.Frequency.ANNUAL:
            if requested_start.month != 1:
                continue
            cycle_start, cycle_end = billing_period_bounds(billing_policy, requested_start)
        elif frequency == CourseBillingPolicy.Frequency.ONE_TIME:
            if (
                billing_policy.effective_from.year != requested_start.year
                or billing_policy.effective_from.month != requested_start.month
            ):
                continue
            cycle_start = cycle_end = billing_policy.effective_from
        else:
            continue
        due = billing_policy.due_date_for(cycle_start.year, cycle_start.month)
        if not billing_policy.is_effective_on(due):
            continue
        for student in _eligible_students(billing_policy):
            eligibility = eligibility_date(student, billing_policy)
            if eligibility and eligibility > cycle_end:
                continue
            installments = (
                int(billing_policy.installments or 1)
                if billing_policy.installment_allowed else 1
            )
            if dry_run:
                planned.append({
                    "student_id": student.pk, "policy_id": billing_policy.pk,
                    "period": period_label(cycle_start, cycle_end),
                })
                continue
            try:
                with transaction.atomic():
                    for index in range(1, max(1, installments) + 1):
                        _invoice, was_created = ensure_invoice(
                            student, billing_policy, period_start=cycle_start,
                            actor=actor, reason=reason or "Avtomatik hisoblash",
                            installment=(index, installments), on_date=due,
                        )
                        created += was_created
            except TuitionError:
                skipped += 1
    return {
        "period_start": requested_start.isoformat(),
        "period_end": requested_end.isoformat(),
        "created": created,
        "skipped": skipped,
        "planned": planned,
        "dry_run": dry_run,
    }


def _eligible_students(policy):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if policy.group_id:
        return User.objects.filter(
            student_groups=policy.group, is_active=True, role="student",
        )
    return User.objects.filter(
        enrollments__course_id=policy.course_id, is_active=True, role="student",
    ).distinct()


def recompute_invoice(invoice: CourseInvoice, *, save: bool = True) -> CourseInvoice:
    """Recompute confirmed and pending payment totals plus the invoice status."""
    if invoice.status in (
        CourseInvoice.Status.CANCELLED, CourseInvoice.Status.WAIVED,
    ):
        return invoice
    totals = invoice.payments.aggregate(
        paid=Sum("amount_uzs", filter=Q(status=CoursePayment.Status.VERIFIED)),
        pending=Sum(
            "amount_uzs", filter=Q(status=CoursePayment.Status.PENDING_VERIFICATION),
        ),
    )
    paid = totals["paid"] or ZERO
    pending = totals["pending"] or ZERO
    invoice.paid_amount_uzs = paid
    invoice.pending_amount_uzs = pending
    balance = invoice.amount_due_uzs - paid
    # ``overdue`` is a *manual* transition: only ``mark_overdue_invoices`` (and
    # the matching admin action) sets it. Recomputing totals must not invent it
    # from the calendar, or a partial payment would relabel a payable invoice and
    # an unrelated correction would flip one to debt collection. An invoice that
    # is *already* overdue stays overdue until it is settled.
    was_overdue = invoice.status == CourseInvoice.Status.OVERDUE
    if invoice.status == CourseInvoice.Status.REFUNDED:
        pass
    elif paid <= 0:
        if pending >= balance and balance > 0:
            invoice.status = CourseInvoice.Status.PENDING_VERIFICATION
        else:
            invoice.status = (
                CourseInvoice.Status.OVERDUE if was_overdue
                else CourseInvoice.Status.UNPAID
            )
    elif balance <= 0 and pending <= 0:
        invoice.status = CourseInvoice.Status.PAID
    elif balance <= 0:
        invoice.status = CourseInvoice.Status.PENDING_VERIFICATION
    else:
        invoice.status = (
            CourseInvoice.Status.PENDING_VERIFICATION if pending >= balance
            else CourseInvoice.Status.OVERDUE if was_overdue
            else CourseInvoice.Status.PARTIALLY_PAID
        )
    if save:
        invoice.save(update_fields=[
            "paid_amount_uzs", "pending_amount_uzs", "status", "updated_at",
        ])
    return invoice


def register_payment(*, student, amount, method, reference: str = "",
                     invoice: CourseInvoice | None = None, proof=None,
                     submitted_by=None, note: str = "") -> CoursePayment:
    """Record a claimed payment; only an authorized verification confirms it."""
    amount = Decimal(str(amount))
    if amount <= 0:
        raise TuitionError("To'lov summasi noldan katta bo'lishi kerak.")
    if invoice is not None and invoice.student_id != student.pk:
        raise TuitionError("To'lov boshqa o'quvchining hisobiga bog'lanmaydi.")
    if invoice is not None and invoice.policy_id:
        accepted_methods = CourseBillingPolicy.objects.filter(
            pk=invoice.policy_id,
        ).values_list("accepted_methods", flat=True).first() or []
        if accepted_methods and method not in accepted_methods:
            raise TuitionError("Bu to'lov usuli siyosatda qabul qilinmagan.")
    caller_invoice = invoice
    with transaction.atomic():
        if invoice is not None:
            invoice = CourseInvoice.objects.select_for_update().select_related(
                "policy",
            ).get(pk=invoice.pk)
            if invoice.status in (
                CourseInvoice.Status.CANCELLED, CourseInvoice.Status.WAIVED,
                CourseInvoice.Status.PAID, CourseInvoice.Status.REFUNDED,
            ):
                raise TuitionError("Bu hisob uchun to'lov qabul qilinmaydi.")
            totals = invoice.payments.aggregate(
                paid=Sum("amount_uzs", filter=Q(status=CoursePayment.Status.VERIFIED)),
                pending=Sum("amount_uzs", filter=Q(
                    status=CoursePayment.Status.PENDING_VERIFICATION,
                )),
            )
            available = invoice.amount_due_uzs - (totals["paid"] or ZERO) - (
                totals["pending"] or ZERO
            )
            if amount > available:
                raise TuitionError("To'lov summasi hisobning qolgan qismidan oshmasligi kerak.")
        payment = CoursePayment.objects.create(
            invoice=invoice, student=student, amount_uzs=amount, method=method,
            reference=(reference or "")[:120], proof=proof, note=note,
            submitted_by=submitted_by,
            status=CoursePayment.Status.PENDING_VERIFICATION,
        )
        _audit(
            TuitionAuditLog.Action.PAYMENT_SUBMITTED, actor=submitted_by,
            student=student, invoice=invoice, payment=payment, new_value=amount,
        )
        if invoice is not None:
            recompute_invoice(invoice)
            if caller_invoice is not invoice:
                for field in (
                    "paid_amount_uzs", "pending_amount_uzs", "status", "updated_at",
                ):
                    setattr(caller_invoice, field, getattr(invoice, field))
                payment.invoice = caller_invoice
    return payment


def verify_payment(payment: CoursePayment, *, actor, reason: str = "") -> CoursePayment:
    """Confirm a payment after a privileged human verification."""
    from .permissions import assert_can_manage_tuition

    assert_can_manage_tuition(actor)
    original_payment = payment
    with transaction.atomic():
        payment = CoursePayment.objects.select_for_update().select_related(
            "verified_by", "invoice",
        ).get(pk=payment.pk)
        if payment.status == CoursePayment.Status.VERIFIED:
            original_payment.status = payment.status
            original_payment.verified_by = payment.verified_by
            original_payment.verified_by_id = payment.verified_by_id
            original_payment.verified_at = payment.verified_at
            original_payment.updated_at = payment.updated_at
            if payment.invoice_id:
                original_payment.invoice = payment.invoice
            return original_payment
        if payment.status != CoursePayment.Status.PENDING_VERIFICATION:
            raise TuitionError("Faqat tekshirilayotgan to'lovni tasdiqlash mumkin.")
        invoice = None
        if payment.invoice_id:
            invoice = CourseInvoice.objects.select_for_update().get(pk=payment.invoice_id)
            confirmed = invoice.payments.filter(
                status=CoursePayment.Status.VERIFIED,
            ).aggregate(total=Sum("amount_uzs"))["total"] or ZERO
            pending_total = invoice.payments.filter(
                status=CoursePayment.Status.PENDING_VERIFICATION,
            ).aggregate(total=Sum("amount_uzs"))["total"] or ZERO
            if confirmed + pending_total > invoice.amount_due_uzs:
                raise TuitionError("Tekshirilayotgan to'lovlar jami invoice summasidan oshadi.")
            if invoice.status in (CourseInvoice.Status.CANCELLED, CourseInvoice.Status.WAIVED):
                raise TuitionError("Bekor qilingan yoki kechirilgan hisobni tasdiqlab bo'lmaydi.")
            available = invoice.amount_due_uzs - confirmed
            if payment.amount_uzs > available:
                raise TuitionError("Tasdiqlangan to'lov invoice qoldig'idan oshib ketadi.")
        payment.status = CoursePayment.Status.VERIFIED
        payment.verified_by = actor
        payment.verified_at = timezone.now()
        payment.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
        _audit(
            TuitionAuditLog.Action.PAYMENT_VERIFIED, actor=actor,
            student=payment.student, invoice=payment.invoice, payment=payment,
            old_value=CoursePayment.Status.PENDING_VERIFICATION,
            new_value=CoursePayment.Status.VERIFIED, reason=reason,
        )
        if invoice is not None:
            recompute_invoice(invoice)
    # Mutate the caller's instance as well as the locked row, preserving the
    # long-standing service contract used by admin/API serializers.
    original_payment.status = CoursePayment.Status.VERIFIED
    original_payment.verified_by = actor
    original_payment.verified_by_id = actor.pk
    original_payment.verified_at = payment.verified_at or timezone.now()
    original_payment.updated_at = payment.updated_at
    if invoice is not None:
        # Keep the original invoice object held by callers coherent with the
        # locked row recomputed above; serializers and service callers commonly
        # retain this object across register_payment() / verify_payment().
        for field in (
            "paid_amount_uzs", "pending_amount_uzs", "status", "updated_at",
        ):
            setattr(original_payment.invoice, field, getattr(invoice, field))
        original_payment.invoice = invoice if original_payment.invoice is None else original_payment.invoice
    if original_payment.invoice_id:
        invoice_id = original_payment.invoice_id
        transaction.on_commit(lambda: _notify_verified(invoice_id))
    return original_payment


def reject_payment(payment: CoursePayment, *, actor, reason: str = "") -> CoursePayment:
    from .permissions import assert_can_manage_tuition

    assert_can_manage_tuition(actor)
    payment.status = CoursePayment.Status.REJECTED
    payment.rejection_reason = (reason or "")[:200]
    payment.verified_by = actor
    payment.verified_at = timezone.now()
    payment.save(update_fields=[
        "status", "rejection_reason", "verified_by", "verified_at", "updated_at",
    ])
    _audit(
        TuitionAuditLog.Action.PAYMENT_REJECTED, actor=actor, student=payment.student,
        invoice=payment.invoice, payment=payment, reason=reason,
    )
    if payment.invoice_id:
        recompute_invoice(payment.invoice)
    return payment


def refund_payment(payment: CoursePayment, *, actor, reason: str = "") -> CoursePayment:
    """Reverse a verified payment without removing enrollment."""
    from .permissions import assert_can_manage_tuition

    assert_can_manage_tuition(actor)
    with transaction.atomic():
        payment = CoursePayment.objects.select_for_update().select_related("invoice").get(pk=payment.pk)
        if payment.status != CoursePayment.Status.VERIFIED:
            raise TuitionError("Faqat tasdiqlangan to'lov qaytarilishi mumkin.")
        payment.status = CoursePayment.Status.REFUNDED
        payment.save(update_fields=["status", "updated_at"])
        _audit(
            TuitionAuditLog.Action.PAYMENT_REFUNDED, actor=actor,
            student=payment.student, invoice=payment.invoice, payment=payment,
            old_value=CoursePayment.Status.VERIFIED,
            new_value=CoursePayment.Status.REFUNDED, reason=reason,
        )
        if payment.invoice_id:
            recompute_invoice(payment.invoice)
    return payment


def adjust_invoice(invoice: CourseInvoice, *, actor, new_amount, reason: str = "") -> CourseInvoice:
    """Correct an invoice amount as an explicit audited adjustment."""
    from .permissions import assert_can_manage_tuition

    assert_can_manage_tuition(actor)
    new_amount = Decimal(str(new_amount))
    if new_amount < 0:
        raise TuitionError("Summa manfiy bo'lishi mumkin emas.")
    old = invoice.amount_due_uzs
    invoice.amount_due_uzs = new_amount
    invoice.status = CourseInvoice.Status.ADJUSTED
    invoice.save(update_fields=["amount_due_uzs", "status", "updated_at"])
    _audit(
        TuitionAuditLog.Action.INVOICE_ADJUSTED, actor=actor, student=invoice.student,
        invoice=invoice, field="amount_due_uzs", old_value=old,
        new_value=new_amount, reason=reason,
    )
    return recompute_invoice(invoice)


def cancel_invoice(invoice: CourseInvoice, *, actor, reason: str = "") -> CourseInvoice:
    from .permissions import assert_can_manage_tuition

    assert_can_manage_tuition(actor)
    old = invoice.status
    invoice.status = CourseInvoice.Status.CANCELLED
    invoice.save(update_fields=["status", "updated_at"])
    _audit(
        TuitionAuditLog.Action.INVOICE_CANCELLED, actor=actor, student=invoice.student,
        invoice=invoice, old_value=old, new_value=invoice.status, reason=reason,
    )
    return invoice


def waive_invoice(invoice: CourseInvoice, *, actor, reason: str = "") -> CourseInvoice:
    from .permissions import assert_can_manage_tuition

    assert_can_manage_tuition(actor)
    invoice.status = CourseInvoice.Status.WAIVED
    invoice.amount_due_uzs = ZERO
    invoice.save(update_fields=["status", "amount_due_uzs", "updated_at"])
    _audit(
        TuitionAuditLog.Action.INVOICE_ADJUSTED, actor=actor, student=invoice.student,
        invoice=invoice, field="status", new_value=invoice.status, reason=reason,
    )
    return invoice


def mark_overdue_invoices(*, as_of: date | None = None, actor=None) -> dict:
    """Flag unpaid invoices past their due date plus grace; does not remove enrollment."""
    as_of = as_of or today()
    candidates = CourseInvoice.objects.filter(
        status__in=(
            CourseInvoice.Status.UNPAID,
            CourseInvoice.Status.PARTIALLY_PAID,
            CourseInvoice.Status.ADJUSTED,
        ), due_date__lt=as_of,
    ).filter(Q(grace_until__isnull=True) | Q(grace_until__lt=as_of))
    marked = 0
    for invoice in candidates:
        if invoice.paid_amount_uzs >= invoice.amount_due_uzs or invoice.amount_due_uzs <= 0:
            continue
        old = invoice.status
        invoice.status = CourseInvoice.Status.OVERDUE
        invoice.save(update_fields=["status", "updated_at"])
        _audit(
            TuitionAuditLog.Action.INVOICE_MARKED_OVERDUE, actor=actor,
            student=invoice.student, invoice=invoice, old_value=old,
            new_value=invoice.status,
        )
        marked += 1
    return {"as_of": as_of.isoformat(), "marked": marked}


def reminder_stage_for(invoice: CourseInvoice, *, as_of: date | None = None,
                       policy: CourseBillingPolicy | None = None) -> str | None:
    """Return the configured reminder stage, if an invoice remains payable."""
    as_of = as_of or today()
    if invoice.status in (
        CourseInvoice.Status.PAID, CourseInvoice.Status.WAIVED,
        CourseInvoice.Status.CANCELLED, CourseInvoice.Status.REFUNDED,
    ):
        return None
    if invoice.amount_due_uzs <= 0 or invoice.balance_uzs <= 0:
        return None
    policy = policy or invoice.policy
    offsets = policy.reminder_offsets() if policy else {
        "before": [], "due": [], "overdue": [],
    }
    if invoice.awaiting_confirmation:
        return PaymentReminderStage.AWAITING_CONFIRMATION
    if as_of < invoice.due_date:
        delta = (invoice.due_date - as_of).days
        return PaymentReminderStage.BEFORE_DUE if delta in offsets["before"] else None
    if as_of == invoice.due_date:
        return PaymentReminderStage.DUE_TODAY if 0 in offsets["due"] else None
    overdue_days = (as_of - invoice.due_date).days
    return PaymentReminderStage.OVERDUE if overdue_days in offsets["overdue"] else None


def in_quiet_hours(policy: CourseBillingPolicy | None, *, now=None) -> bool:
    """Respect policy quiet hours in the configured local timezone."""
    offsets = policy.reminder_offsets() if policy else {"quiet_start": 21, "quiet_end": 8}
    start, end = offsets["quiet_start"], offsets["quiet_end"]
    instant = now or timezone.now()
    if timezone.is_naive(instant):
        instant = timezone.make_aware(instant, timezone.get_current_timezone())
    reminder_timezone = timezone.get_current_timezone()
    if policy is not None:
        configured_timezone = (policy.reminder_policy or {}).get("timezone")
        if configured_timezone:
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

            try:
                reminder_timezone = ZoneInfo(str(configured_timezone))
            except (ZoneInfoNotFoundError, ValueError):
                reminder_timezone = timezone.get_current_timezone()
    hour = timezone.localtime(instant, reminder_timezone).hour
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def reminders_due(*, as_of: date | None = None, limit: int = 500,
                  now=None) -> list[dict]:
    """Select invoices and verified recipients prescribed by the reminder ladder."""
    as_of = as_of or today()
    invoices = CourseInvoice.objects.filter(
        status__in=OPEN_STATUSES,
    ).select_related("policy", "student").order_by("due_date")[:limit]
    out = []
    for invoice in invoices:
        if invoice.policy and in_quiet_hours(invoice.policy, now=now):
            continue
        stage = reminder_stage_for(invoice, as_of=as_of)
        if stage is None:
            continue
        for recipient in reminder_recipients(invoice.student):
            out.append({
                "invoice_id": invoice.pk,
                "stage": stage,
                "recipient_id": recipient.pk,
                "student_id": invoice.student_id,
            })
    return out


def reminder_recipients(student) -> list:
    """The student and only their verified, approved parents."""
    from apps.accounts.models import ParentStudentLink

    recipients = []
    if getattr(student, "is_active", False):
        recipients.append(student)
    for link in ParentStudentLink.objects.filter(
        student=student, is_approved=True,
    ).select_related("parent"):
        if link.parent and link.parent.is_active:
            recipients.append(link.parent)
    return recipients


def _notify_verified(invoice_id: int) -> None:
    from . import notifications

    try:
        notifications.send_payment_confirmed(invoice_id)
    except Exception:
        logger.exception("Payment confirmation notification failed for invoice %s", invoice_id)


def student_tuition_overview(student, *, limit: int = 24) -> dict:
    """Tuition overview limited to the selected student."""
    invoices = CourseInvoice.objects.filter(student=student).select_related("policy")
    open_invoices = invoices.filter(status__in=OPEN_STATUSES)
    outstanding = open_invoices.aggregate(total=Sum("amount_due_uzs"))["total"] or ZERO
    paid = open_invoices.aggregate(total=Sum("paid_amount_uzs"))["total"] or ZERO
    latest = invoices.order_by("-billing_period_start", "-pk").first()
    return {
        "student_id": student.pk,
        "student_name": student.get_full_name() or student.email,
        "invoices_total": invoices.count(),
        "open_invoices": open_invoices.count(),
        "outstanding_uzs": float(max(ZERO, outstanding - paid)),
        "confirmed_paid_uzs": float(
            invoices.aggregate(total=Sum("paid_amount_uzs"))["total"] or ZERO
        ),
        "status": latest.status if latest else None,
        "status_label": latest.status_label if latest else None,
        "invoices": [
            {
                "id": invoice.pk,
                "period_label": invoice.period_label,
                "amount_due_uzs": float(invoice.amount_due_uzs),
                "paid_amount_uzs": float(invoice.paid_amount_uzs),
                "pending_amount_uzs": float(invoice.pending_amount_uzs),
                "balance_uzs": float(invoice.balance_uzs),
                "due_date": invoice.due_date.isoformat(),
                "status": invoice.status,
                "status_label": invoice.status_label,
                "awaiting_confirmation": invoice.awaiting_confirmation,
            }
            for invoice in invoices.order_by("-billing_period_start", "-pk")[:limit]
        ],
    }


def children_tuition_overview(parent) -> list[dict]:
    """Return only approved linked children."""
    from apps.accounts.models import ParentStudentLink

    children = ParentStudentLink.objects.filter(
        parent=parent, is_approved=True,
    ).select_related("student")
    return [
        student_tuition_overview(link.student, limit=6)
        for link in children
        if link.student and link.student.is_active
    ]


def group_finance_summary(group: StudentGroup, period_start, period_end) -> dict:
    """Aggregate only the group-scoped finances; never expose student details."""
    start_date = period_start.date() if hasattr(period_start, "date") else period_start
    end_date = period_end.date() if hasattr(period_end, "date") else period_end
    students = group.students.filter(is_active=True)
    group_policy = Q(policy__group=group)
    course_ids = Enrollment.objects.filter(
        student__in=students,
    ).values_list("course_id", flat=True).distinct()
    group_policy |= Q(policy__course_id__in=course_ids)
    group_invoices = CourseInvoice.objects.filter(student__in=students).filter(group_policy)
    in_period = group_invoices.filter(
        billing_period_start__lte=end_date,
        billing_period_end__gte=start_date,
    )
    open_totals = in_period.filter(status__in=OPEN_STATUSES).aggregate(
        billed=Sum("amount_due_uzs"), paid=Sum("paid_amount_uzs"),
    )
    billed = in_period.aggregate(total=Sum("amount_due_uzs"))["total"] or ZERO
    paid = in_period.aggregate(total=Sum("paid_amount_uzs"))["total"] or ZERO
    return {        "policy_configured": in_period.exists() or CourseBillingPolicy.objects.filter(

            Q(group=group) | Q(course__enrollments__student__in=students), is_active=True,
        ).exists(),
        "period_invoices": in_period.count(),
        "paid_count": in_period.filter(status=CourseInvoice.Status.PAID)
        .values("student_id").distinct().count(),
        "partial_count": in_period.filter(status=CourseInvoice.Status.PARTIALLY_PAID)
        .values("student_id").distinct().count(),
        "unpaid_count": in_period.filter(status__in=(
            CourseInvoice.Status.UNPAID, CourseInvoice.Status.PENDING_VERIFICATION,
        )).values("student_id").distinct().count(),
        "overdue_count": in_period.filter(status=CourseInvoice.Status.OVERDUE)
        .values("student_id").distinct().count(),
        "billed_uzs": float(billed),
        "confirmed_paid_uzs": float(paid),
        "outstanding_uzs": float(max(
            ZERO,
            (open_totals["billed"] or ZERO) - (open_totals["paid"] or ZERO),
        )),
    }
