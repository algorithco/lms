"""Course-tuition JSON API.

Mounted beside the existing school/billing blocks and deliberately thin: every
rule — balances, the payment lifecycle, reminder state — lives in
``apps.tuition.services``. Two things are enforced *here* because they are HTTP
concerns:

* a student or parent may read only their own (or their verified child's)
  tuition, and the queryset is scoped before anything else runs;
* ``POST payments`` records a *claim*. It never marks an invoice paid, and the
  verify/reject/refund routes require the tuition permission, so a student
  cannot approve their own receipt.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_date

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.accounts.access import is_platform_admin
from apps.courses.models import StudentGroup
from apps.tuition import services
from apps.tuition.models import (
    CourseBillingPolicy,
    CourseInvoice,
    CoursePayment,
    PaymentMethod,
    TuitionAuditLog,
)
from apps.tuition.permissions import (
    can_manage_tuition,
    can_view_invoice,
    can_view_student_tuition,
    can_view_tuition,
)

from .permissions import IsPanelAdmin, IsTeacherOrAdmin
from .serializers import (
    CourseBillingPolicySerializer,
    InvoiceDueDateSerializer,
    TuitionPaymentSubmissionSerializer,
)

OPEN_STATUSES = services.OPEN_STATUSES


def _serialize_invoice(invoice: CourseInvoice) -> dict:
    return {
        "id": invoice.pk,
        "student_id": invoice.student_id,
        "student_name": invoice.student.get_full_name() or invoice.student.email,
        "period_label": invoice.period_label,
        "course": invoice.course.title if invoice.course_id else None,
        "amount_due_uzs": float(invoice.amount_due_uzs),
        "paid_amount_uzs": float(invoice.paid_amount_uzs),
        "pending_amount_uzs": float(invoice.pending_amount_uzs),
        "balance_uzs": float(invoice.balance_uzs),
        "due_date": invoice.due_date.isoformat(),
        "grace_until": invoice.grace_until.isoformat() if invoice.grace_until else None,
        "status": invoice.status,
        "status_label": invoice.status_label,
        "is_installment": invoice.is_installment,
        "installment_number": invoice.installment_number,
        "awaiting_confirmation": invoice.awaiting_confirmation,
        "payment_instructions": (
            invoice.policy.payment_instructions if invoice.policy_id else ""
        ),
    }


def _serialize_payment(payment: CoursePayment) -> dict:
    # The student and the invoice period are included so an operator can act on a
    # receipt without a second lookup. Every caller has already established the
    # right to this student's finances (own record, approved parent, or the
    # explicit tuition permission), so this adds no reach — only the identity of
    # the row's own owner.
    return {
        "id": payment.pk,
        "invoice_id": payment.invoice_id,
        "student_id": payment.student_id,
        "student_name": (payment.student.get_full_name() or payment.student.email)
        if payment.student_id
        else "",
        "invoice_period": (
            payment.invoice.period_label if payment.invoice_id else None
        ),
        "amount_uzs": float(payment.amount_uzs),
        "method": payment.method,
        "method_label": payment.get_method_display(),
        "reference": payment.reference,
        "status": payment.status,
        "status_label": payment.get_status_display(),
        "verified_at": payment.verified_at.isoformat() if payment.verified_at else None,
        "created_at": payment.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Student / parent facing
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_tuition_view(request):
    """The caller's own tuition position (never another student's)."""
    data = services.student_tuition_overview(request.user)
    data["invoices"] = [
        _serialize_invoice(invoice)
        for invoice in CourseInvoice.objects.filter(student=request.user)
        .select_related("student", "policy", "course")
        .order_by("-billing_period_start", "-pk")[:24]
    ]
    data["payments"] = [
        _serialize_payment(payment)
        for payment in CoursePayment.objects.filter(student=request.user)
        .select_related("student", "invoice")
        .order_by("-created_at")[:20]
    ]
    data["accepted_methods"] = [
        {"value": value, "label": label} for value, label in PaymentMethod.choices
    ]
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def invoice_detail_view(request, invoice_id: int):
    invoice = (
        CourseInvoice.objects.filter(pk=invoice_id)
        .select_related(
            "student",
            "policy",
            "course",
        )
        .first()
    )
    if invoice is None or not can_view_invoice(request.user, invoice):
        return Response({"detail": "Hisob-faktura topilmadi."}, status=404)
    payments = (
        CoursePayment.objects.filter(
            invoice=invoice,
        )
        .select_related("student", "invoice")
        .order_by("-created_at")
    )
    return Response(
        {
            "invoice": _serialize_invoice(invoice),
            "payments": [_serialize_payment(payment) for payment in payments],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payment_detail_view(request, payment_id: int):
    """Return verification status only to the student, an approved parent or finance staff."""
    payment = (
        CoursePayment.objects.filter(pk=payment_id)
        .select_related(
            "invoice",
            "student",
        )
        .first()
    )
    if payment is None or not can_view_student_tuition(request.user, payment.student):
        return Response({"detail": "To'lov topilmadi."}, status=404)
    return Response(
        {
            "payment": _serialize_payment(payment),
            "invoice": _serialize_invoice(payment.invoice)
            if payment.invoice_id
            else None,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def child_tuition_view(request):
    """Verified children's tuition for a parent (unapproved links yield nothing)."""
    children = services.children_tuition_overview(request.user)
    grouped = {child["student_id"]: child for child in children}
    for invoices in CourseInvoice.objects.filter(
        student_id__in=list(grouped),
    ).select_related("student", "policy", "course"):
        grouped[invoices.student_id].setdefault("invoice_rows", []).append(
            _serialize_invoice(invoices),
        )
    return Response({"children": list(grouped.values())})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_payment_view(request):
    """Record a payment *claim*. An administrator still has to confirm it."""
    serializer = TuitionPaymentSubmissionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    payload = serializer.validated_data
    invoice_id = payload["invoice_id"]
    invoice = (
        CourseInvoice.objects.filter(pk=invoice_id)
        .select_related("student", "policy", "course")
        .first()
    )
    if invoice is None:
        return Response({"detail": "Hisob-faktura topilmadi."}, status=404)
    if not can_view_invoice(request.user, invoice):
        # Never disclose whether someone else's invoice exists.
        return Response({"detail": "Hisob-faktura topilmadi."}, status=404)
    if invoice.status in (
        CourseInvoice.Status.CANCELLED,
        CourseInvoice.Status.WAIVED,
        CourseInvoice.Status.PAID,
    ):
        return Response(
            {"detail": "Bu hisob uchun to'lov qabul qilinmaydi."}, status=409
        )

    method = payload.get("method") or PaymentMethod.CARD
    accepted_methods = invoice.policy.accepted_methods if invoice.policy_id else []
    if accepted_methods and method not in accepted_methods:
        return Response(
            {"detail": "Bu to'lov usuli siyosatda qabul qilinmagan."}, status=400
        )
    if invoice.balance_uzs <= 0:
        return Response({"detail": "Hisobda to'lanadigan qoldiq yo'q."}, status=409)
    if payload["amount"] > Decimal(str(invoice.balance_uzs)):
        return Response(
            {"detail": "To'lov summasi hisob qoldig'idan oshmasligi kerak."}, status=400
        )
    try:
        with transaction.atomic():
            invoice = (
                CourseInvoice.objects.select_for_update()
                .select_related(
                    "student",
                    "policy",
                    "course",
                )
                .get(pk=invoice.pk)
            )
            if not can_view_invoice(request.user, invoice):
                return Response({"detail": "Hisob-faktura topilmadi."}, status=404)
            if payload["amount"] > Decimal(str(invoice.balance_uzs)):
                return Response(
                    {"detail": "To'lov summasi hisob qoldig'idan oshmasligi kerak."},
                    status=400,
                )
            payment = services.register_payment(
                student=invoice.student,
                amount=payload["amount"],
                method=method,
                reference=payload.get("reference", ""),
                proof=payload.get("proof"),
                invoice=invoice,
                submitted_by=request.user,
                note=payload.get("note", ""),
            )
    except services.TuitionError as exc:
        return Response({"detail": str(exc)}, status=400)
    except IntegrityError:
        return Response({"detail": "Bu to'lov raqami avval yuborilgan."}, status=409)
    except (ValidationError, ValueError, InvalidOperation) as exc:
        return Response({"detail": str(exc)}, status=400)

    invoice.refresh_from_db()
    return Response(
        {
            "payment": _serialize_payment(payment),
            "invoice": _serialize_invoice(invoice),
        },
        status=201,
    )


# ---------------------------------------------------------------------------
# Teacher / admin facing
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsTeacherOrAdmin])
def group_tuition_view(request):
    """Aggregate tuition for one of the caller's groups.

    Teachers see this **only** with the tuition view permission — group
    ownership is not a financial privilege.
    """
    if not can_view_tuition(request.user):
        return Response(
            {"detail": "To'lov hisobotini ko'rish huquqi yo'q."}, status=403
        )
    group_id = request.query_params.get("group_id")
    group = StudentGroup.objects.filter(pk=group_id).first() if group_id else None
    if group is None:
        return Response({"detail": "Guruh topilmadi."}, status=404)
    if not is_platform_admin(request.user) and group.teacher_id != request.user.pk:
        return Response({"detail": "Guruh topilmadi."}, status=404)

    today = services.today()
    period_start, period_end = services.month_bounds(today)
    summary = services.group_finance_summary(group, period_start, period_end)
    summary["group_id"] = group.pk
    summary["group_name"] = group.name
    return Response(summary)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def invoice_list_view(request):
    """Authorized invoice list with filters; teachers need explicit finance view permission."""
    if not can_view_tuition(request.user):
        return Response(
            {"detail": "To'lov ma'lumotlarini ko'rish huquqi yo'q."}, status=403
        )
    qs = CourseInvoice.objects.select_related("student", "policy", "course")
    if not is_platform_admin(request.user):
        qs = qs.filter(student__student_groups__teacher=request.user)
    status_filter = request.query_params.get("status")
    if status_filter == "open":
        qs = qs.filter(status__in=OPEN_STATUSES)
    elif status_filter:
        qs = qs.filter(status=status_filter)
    student_id = request.query_params.get("student_id")
    if student_id:
        qs = qs.filter(student_id=student_id)
    group_id = request.query_params.get("group_id")
    if group_id:
        qs = qs.filter(student__student_groups__pk=group_id)
        if not is_platform_admin(request.user):
            qs = qs.filter(student__student_groups__teacher=request.user)
    try:
        limit = min(max(int(request.query_params.get("limit", 50) or 50), 1), 200)
        offset = max(int(request.query_params.get("offset", 0) or 0), 0)
    except (TypeError, ValueError):
        return Response({"detail": "Sahifalash parametrlari noto'g'ri."}, status=400)
    count = qs.distinct().count()
    rows = list(
        qs.distinct().order_by("-billing_period_start", "-pk")[offset : offset + limit]
    )
    return Response({"count": count, "results": [_serialize_invoice(r) for r in rows]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def billing_policy_list_view(request):
    if not can_view_tuition(request.user):
        return Response(
            {"detail": "To'lov siyosatlarini ko'rish huquqi yo'q."}, status=403
        )
    queryset = CourseBillingPolicy.objects.select_related("course", "group").order_by(
        "-effective_from",
        "name",
    )
    if request.query_params.get("active") in ("1", "true"):
        queryset = queryset.filter(is_active=True)
    return Response(
        {
            "count": queryset.count(),
            "results": CourseBillingPolicySerializer(queryset[:200], many=True).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def billing_policy_create_view(request):
    if not can_manage_tuition(request.user):
        return Response(
            {"detail": "To'lov siyosatini boshqarish huquqi yo'q."}, status=403
        )
    serializer = CourseBillingPolicySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        policy = serializer.save()
        TuitionAuditLog.objects.create(
            actor=request.user,
            action=TuitionAuditLog.Action.POLICY_CREATED,
            policy=policy,
            field="policy",
            new_value=str(policy.amount_uzs),
            reason="Web API orqali yaratildi",
        )
    return Response(CourseBillingPolicySerializer(policy).data, status=201)


@api_view(["GET", "PATCH", "PUT"])
@permission_classes([IsAuthenticated])
def billing_policy_detail_view(request, policy_id: int):
    policy = get_object_or_404(
        CourseBillingPolicy.objects.select_related("course", "group"), pk=policy_id
    )
    if not is_platform_admin(request.user):
        owned_scope = (
            policy.group_id and policy.group.teacher_id == request.user.pk
        ) or (policy.course_id and policy.course.teacher_id == request.user.pk)
        if not owned_scope:
            return Response({"detail": "Siyosat topilmadi."}, status=404)
    if request.method == "GET":
        if not can_view_tuition(request.user):
            return Response(
                {"detail": "To'lov siyosatini ko'rish huquqi yo'q."}, status=403
            )
        return Response(CourseBillingPolicySerializer(policy).data)
    if not can_manage_tuition(request.user):
        return Response(
            {"detail": "To'lov siyosatini boshqarish huquqi yo'q."}, status=403
        )
    old_amount = policy.amount_uzs
    serializer = CourseBillingPolicySerializer(
        policy,
        data=request.data,
        partial=request.method == "PATCH",
    )
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        policy = serializer.save()
        TuitionAuditLog.objects.create(
            actor=request.user,
            action=TuitionAuditLog.Action.POLICY_UPDATED,
            policy=policy,
            field="amount_uzs",
            old_value=str(old_amount),
            new_value=str(policy.amount_uzs),
            reason="Web API orqali o'zgartirildi",
        )
    return Response(CourseBillingPolicySerializer(policy).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payment_queue_view(request):
    """Receipts awaiting confirmation — only the explicit tuition operator can read it."""
    from apps.tuition.permissions import can_manage_tuition

    if not can_manage_tuition(request.user):
        return Response({"detail": "To'lovlarni tekshirish huquqi yo'q."}, status=403)
    qs = CoursePayment.objects.select_related("student", "invoice")
    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    else:
        qs = qs.filter(status=CoursePayment.Status.PENDING_VERIFICATION)
    try:
        limit = min(max(int(request.query_params.get("limit", 50) or 50), 1), 200)
        offset = max(int(request.query_params.get("offset", 0) or 0), 0)
    except (TypeError, ValueError):
        return Response({"detail": "Sahifalash parametrlari noto'g'ri."}, status=400)
    count = qs.count()
    rows = list(qs.order_by("created_at")[offset : offset + limit])
    return Response({"count": count, "results": [_serialize_payment(r) for r in rows]})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_payment_view(request, payment_id: int):
    """Confirm a receipt. Only an authorized tuition operator can reach this."""
    if not can_manage_tuition(request.user):
        return Response({"detail": "To'lovni tasdiqlash huquqi yo'q."}, status=403)
    payment = CoursePayment.objects.filter(pk=payment_id).first()
    if payment is None:
        return Response({"detail": "To'lov topilmadi."}, status=404)
    try:
        payment = services.verify_payment(
            payment,
            actor=request.user,
            reason=str(request.data.get("reason") or "Panel orqali tasdiqlandi"),
        )
    except PermissionDenied:
        return Response({"detail": "Ruxsat yo'q."}, status=403)
    except services.TuitionError as exc:
        return Response({"detail": str(exc)}, status=400)
    if payment.invoice_id:
        payment.invoice.refresh_from_db()
    return Response(
        {
            "payment": _serialize_payment(payment),
            "invoice": _serialize_invoice(payment.invoice)
            if payment.invoice_id
            else None,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reject_payment_view(request, payment_id: int):
    if not can_manage_tuition(request.user):
        return Response({"detail": "To'lovni rad etish huquqi yo'q."}, status=403)
    payment = CoursePayment.objects.filter(pk=payment_id).first()
    if payment is None:
        return Response({"detail": "To'lov topilmadi."}, status=404)
    try:
        services.reject_payment(
            payment,
            actor=request.user,
            reason=str(request.data.get("reason") or ""),
        )
    except PermissionDenied:
        return Response({"detail": "Ruxsat yo'q."}, status=403)
    if payment.invoice_id:
        payment.invoice.refresh_from_db()
    return Response(
        {
            "payment": _serialize_payment(payment),
            "invoice": _serialize_invoice(payment.invoice)
            if payment.invoice_id
            else None,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def record_invoice_payment_view(request, invoice_id: int):
    """Record an offline payment after privileged staff confirm the evidence."""
    if not can_manage_tuition(request.user):
        return Response({"detail": "To'lov yozish huquqi yo'q."}, status=403)
    invoice = (
        CourseInvoice.objects.filter(pk=invoice_id)
        .select_related(
            "student",
            "policy",
            "course",
        )
        .first()
    )
    if invoice is None:
        return Response({"detail": "Hisob-faktura topilmadi."}, status=404)
    reason = str(request.data.get("reason") or "").strip()
    if len(reason) < 3:
        return Response(
            {"detail": "Tasdiqlash sababi kamida 3 belgidan iborat bo'lishi kerak."},
            status=400,
        )
    serializer = TuitionPaymentSubmissionSerializer(
        data={
            "invoice_id": invoice.pk,
            "amount": request.data.get("amount"),
            "method": request.data.get("method", PaymentMethod.CASH),
            "reference": request.data.get("reference", ""),
            "note": reason,
        }
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    try:
        with transaction.atomic():
            invoice = (
                CourseInvoice.objects.select_for_update()
                .select_related(
                    "student",
                    "policy",
                    "course",
                )
                .get(pk=invoice.pk)
            )
            payment = services.register_payment(
                student=invoice.student,
                invoice=invoice,
                amount=serializer.validated_data["amount"],
                method=serializer.validated_data["method"],
                reference=serializer.validated_data.get("reference", ""),
                submitted_by=request.user,
                note=reason,
            )
            payment = services.verify_payment(
                payment, actor=request.user, reason=reason
            )
    except IntegrityError:
        return Response({"detail": "Bu to'lov raqami avval yozilgan."}, status=409)
    except (
        services.TuitionError,
        ValidationError,
        ValueError,
        InvalidOperation,
    ) as exc:
        return Response({"detail": str(exc)}, status=400)
    invoice.refresh_from_db()
    return Response(
        {
            "payment": _serialize_payment(payment),
            "invoice": _serialize_invoice(invoice),
        },
        status=201,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def adjust_invoice_view(request, invoice_id: int):
    """Correct an invoice amount — always an explicit, audited adjustment."""
    if not can_manage_tuition(request.user):
        return Response({"detail": "Hisobni o'zgartirish huquqi yo'q."}, status=403)
    invoice = (
        CourseInvoice.objects.filter(pk=invoice_id).select_related("student").first()
    )
    if invoice is None:
        return Response({"detail": "Hisob-faktura topilmadi."}, status=404)
    raw_amount = request.data.get("amount")
    reason = str(request.data.get("reason") or "").strip()
    if raw_amount in (None, "") or len(reason) < 3:
        return Response(
            {"detail": "Summa va kamida 3 belgili sabab kerak."}, status=400
        )
    try:
        services.adjust_invoice(
            invoice,
            actor=request.user,
            new_amount=raw_amount,
            reason=reason,
        )
    except PermissionDenied:
        return Response({"detail": "Ruxsat yo'q."}, status=403)
    except (services.TuitionError, TypeError, ValueError, InvalidOperation) as exc:
        return Response({"detail": str(exc) or "Summa noto'g'ri."}, status=400)
    invoice.refresh_from_db()
    return Response({"invoice": _serialize_invoice(invoice)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def waive_invoice_view(request, invoice_id: int):
    if not can_manage_tuition(request.user):
        return Response({"detail": "Ruxsat yo'q."}, status=403)
    invoice = (
        CourseInvoice.objects.filter(pk=invoice_id)
        .select_related("student", "policy")
        .first()
    )
    if invoice is None:
        return Response({"detail": "Hisob-faktura topilmadi."}, status=404)
    if (
        not is_platform_admin(request.user)
        and invoice.student.student_groups.filter(
            teacher=request.user,
        ).exists()
        is False
    ):
        return Response({"detail": "Hisob-faktura topilmadi."}, status=404)
    reason = str(request.data.get("reason") or "").strip()
    if len(reason) < 3:
        return Response(
            {"detail": "Sabab kamida 3 belgidan iborat bo'lishi kerak."}, status=400
        )
    try:
        services.waive_invoice(invoice, actor=request.user, reason=reason)
    except PermissionDenied:
        return Response({"detail": "Ruxsat yo'q."}, status=403)
    invoice.refresh_from_db()
    return Response({"invoice": _serialize_invoice(invoice)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_invoice_overdue_view(request, invoice_id: int):
    if not can_manage_tuition(request.user):
        return Response({"detail": "Ruxsat yo'q."}, status=403)
    invoice = (
        CourseInvoice.objects.filter(pk=invoice_id).select_related("student").first()
    )
    if invoice is None:
        return Response({"detail": "Hisob-faktura topilmadi."}, status=404)
    serializer = InvoiceDueDateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    old_due_date = invoice.due_date
    old_grace_until = invoice.grace_until
    invoice.due_date = serializer.validated_data["due_date"]
    invoice.grace_until = serializer.validated_data.get("grace_until", old_grace_until)
    invoice.save(update_fields=["due_date", "grace_until", "updated_at"])
    TuitionAuditLog.objects.create(
        actor=request.user,
        action=TuitionAuditLog.Action.INVOICE_UPDATED,
        invoice=invoice,
        student=invoice.student,
        field="due_date",
        old_value=old_due_date.isoformat(),
        new_value=invoice.due_date.isoformat(),
        reason="Admin panel orqali muddat yangilandi",
    )
    if old_grace_until != invoice.grace_until:
        TuitionAuditLog.objects.create(
            actor=request.user,
            action=TuitionAuditLog.Action.INVOICE_UPDATED,
            invoice=invoice,
            student=invoice.student,
            field="grace_until",
            old_value=old_grace_until.isoformat() if old_grace_until else "",
            new_value=invoice.grace_until.isoformat() if invoice.grace_until else "",
            reason="Admin panel orqali imtiyoz muddati yangilandi",
        )
    return Response({"invoice": _serialize_invoice(invoice)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tuition_audit_view(request):
    """The append-only correction trail for one student or invoice."""
    if not can_manage_tuition(request.user):
        return Response(
            {"detail": "Audit yozuvlarini ko'rish huquqi yo'q."}, status=403
        )
    qs = TuitionAuditLog.objects.select_related(
        "actor", "student", "invoice", "payment"
    )
    if request.query_params.get("invoice_id"):
        qs = qs.filter(invoice_id=request.query_params["invoice_id"])
    if request.query_params.get("student_id"):
        qs = qs.filter(student_id=request.query_params["student_id"])
    if request.query_params.get("payment_id"):
        qs = qs.filter(payment_id=request.query_params["payment_id"])
    action_filter = request.query_params.get("action")
    if action_filter:
        qs = qs.filter(action=action_filter)
    try:
        limit = min(max(int(request.query_params.get("limit", 100) or 100), 1), 200)
    except (TypeError, ValueError):
        return Response({"detail": "limit noto'g'ri."}, status=400)
    rows = list(qs.order_by("-created_at")[:limit])
    return Response(
        {
            "count": len(rows),
            "results": [
                {
                    "id": row.pk,
                    "action": row.action,
                    "action_label": row.get_action_display(),
                    "actor_id": row.actor_id,
                    "actor_name": (row.actor.get_full_name() or row.actor.email)
                    if row.actor_id
                    else None,
                    "field": row.field,
                    "old_value": row.old_value,
                    "new_value": row.new_value,
                    "reason": row.reason,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_student_tuition_view(request, student_id: int):
    """One student's tuition position for an authorized finance reader."""
    student = get_user_model().objects.filter(pk=student_id, role="student").first()
    if student is None or not can_view_student_tuition(request.user, student):
        return Response({"detail": "O'quvchi topilmadi."}, status=404)
    overview = services.student_tuition_overview(student)
    overview["invoices"] = [
        _serialize_invoice(invoice)
        for invoice in CourseInvoice.objects.filter(student=student)
        .select_related("student", "policy", "course")
        .order_by("-billing_period_start", "-pk")[:24]
    ]
    overview["payments"] = [
        _serialize_payment(payment)
        for payment in CoursePayment.objects.filter(student=student)
        .select_related("student", "invoice")
        .order_by("-created_at")[:20]
    ]
    return Response(overview)
