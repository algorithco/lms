"""
Teacher CRM & Financial Overview Views (2-Modul & 3-Modul).
Manages student tuition schedules, debt tracking, 1-click reminders, and Click/Payme receipt OCR.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import ParentStudentRelation, User
from apps.courses.models import StudentGroup, GroupEnrollment
def send_telegram_message_safe(chat_id: int | str, text: str) -> bool:
    """Safely send telegram message using TelegramService or direct requests without raising."""
    try:
        from apps.notifications.services.telegram_service import TelegramService
        TelegramService.send_message(chat_id=int(chat_id), text=text)
        return True
    except Exception as e:
        logger.warning("Telegram send failed to %s: %s", chat_id, e)
        return False
from apps.payments.receipt_scanner import scan_receipt_image

logger = logging.getLogger(__name__)


def sync_group_students(group: StudentGroup):
    """Ensure every student in group.students has an active GroupEnrollment."""
    existing_student_ids = set(group.group_enrollments.values_list("student_id", flat=True))
    all_students = group.students.all()
    today = timezone.localdate()

    for st in all_students:
        if st.id not in existing_student_ids:
            # Check if parent info exists in ParentStudentRelation
            parent_rel = ParentStudentRelation.objects.filter(student=st, is_verified=True).first()
            p_phone = parent_rel.parent_phone if parent_rel else ""
            p_tg = str(parent_rel.parent_telegram_id) if parent_rel and parent_rel.parent_telegram_id else ""

            GroupEnrollment.objects.create(
                group=group,
                student=st,
                monthly_fee=Decimal(str(group.monthly_fee or 400000)),
                billing_cycle_day=10,
                last_payment_date=today,
                next_payment_due=today + timezone.timedelta(days=30),
                payment_status=GroupEnrollment.PaymentStatus.PAID,
                parent_phone=p_phone,
                parent_telegram_id=p_tg,
            )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def group_finance_summary_view(request, group_id):
    """
    Ustoz uchun guruh moliyaviy xulosasi (Mini CRM).
    GET /api/v1/courses/groups/<group_id>/finance-summary/
    """
    group = get_object_or_404(StudentGroup, id=group_id)

    # Ruxsat: guruh ustozi yoki platform admin
    if group.teacher != request.user and not request.user.is_staff and not request.user.is_superuser:
        return Response({"error": "Faqat guruh ustozi moliyaviy hisobotni ko'ra oladi."}, status=403)

    sync_group_students(group)

    enrollments = group.group_enrollments.select_related("student", "student__profile").filter(is_active=True)
    today = timezone.localdate()

    # Statuslarni yangilash
    for e in enrollments:
        e.update_status(today)

    total_students = enrollments.count()
    paid_enrollments = [e for e in enrollments if e.payment_status == GroupEnrollment.PaymentStatus.PAID]
    overdue_enrollments = [e for e in enrollments if e.payment_status == GroupEnrollment.PaymentStatus.OVERDUE]
    due_soon_enrollments = [e for e in enrollments if e.payment_status == GroupEnrollment.PaymentStatus.DUE_SOON]
    debtor_enrollments = overdue_enrollments + due_soon_enrollments

    collected_amount = sum(float(e.monthly_fee) for e in paid_enrollments)
    pending_amount = sum(float(e.monthly_fee) for e in debtor_enrollments)

    students_list = []
    for e in enrollments:
        st = e.student
        days_left = (e.next_payment_due - today).days if e.next_payment_due else 0
        students_list.append({
            "id": e.id,
            "student_id": st.id,
            "full_name": st.get_full_name(),
            "email": st.email,
            "phone": getattr(st.profile, "phone", "") if hasattr(st, "profile") else "",
            "parent_phone": e.parent_phone,
            "parent_telegram_id": e.parent_telegram_id,
            "monthly_fee": float(e.monthly_fee),
            "billing_cycle_day": e.billing_cycle_day,
            "last_payment_date": e.last_payment_date.strftime("%Y-%m-%d") if e.last_payment_date else None,
            "next_payment_due": e.next_payment_due.strftime("%Y-%m-%d") if e.next_payment_due else None,
            "payment_status": e.payment_status,
            "days_left": days_left,
            "has_pro": st.has_pro_access,
        })

    # Ustozning kvota balansi
    teacher_prof = getattr(group.teacher, "teacher_profile", None)
    pro_quota = teacher_prof.pro_quota_balance if teacher_prof else 0
    premium_quota = teacher_prof.premium_quota_balance if teacher_prof else 0

    return Response({
        "group_id": group.id,
        "group_name": group.name,
        "teacher_name": group.teacher.get_full_name(),
        "pro_quota_balance": pro_quota,
        "premium_quota_balance": premium_quota,
        "total_students": total_students,
        "paid_count": len(paid_enrollments),
        "overdue_count": len(overdue_enrollments),
        "due_soon_count": len(due_soon_enrollments),
        "collected_amount": collected_amount,
        "pending_amount": pending_amount,
        "students": students_list,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def record_group_payment_view(request, group_id):
    """
    Ustoz o'quvchidan to'lov qabul qilganda to'lov sanasini 30 kunga uzaytirish.
    POST /api/v1/courses/groups/<group_id>/record-payment/
    """
    group = get_object_or_404(StudentGroup, id=group_id)
    if group.teacher != request.user and not request.user.is_staff:
        return Response({"error": "Ruxsat etilmagan."}, status=403)

    student_id = request.data.get("student_id")
    amount = request.data.get("amount")
    extend_days = int(request.data.get("extend_days", 30))

    enrollment = get_object_or_404(GroupEnrollment, group=group, student_id=student_id)
    enrollment.record_payment(amount=amount, extend_days=extend_days)

    return Response({
        "status": "success",
        "message": f"{enrollment.student.get_full_name()} to'lovi qabul qilindi.",
        "next_payment_due": enrollment.next_payment_due.strftime("%Y-%m-%d"),
        "payment_status": enrollment.payment_status,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_group_payment_reminders_view(request, group_id):
    """
    [ 📢 Barcha qarzdorlarga eslatma yuborish ] bitta bosishli ommaviy tugma.
    POST /api/v1/courses/groups/<group_id>/send-payment-reminders/
    """
    group = get_object_or_404(StudentGroup, id=group_id)
    if group.teacher != request.user and not request.user.is_staff:
        return Response({"error": "Faqat guruh ustozi eslatma yubora oladi."}, status=403)

    today = timezone.localdate()
    enrollments = group.group_enrollments.filter(is_active=True)

    sent_students = 0
    sent_parents = 0

    for e in enrollments:
        e.update_status(today)
        if e.payment_status in (GroupEnrollment.PaymentStatus.OVERDUE, GroupEnrollment.PaymentStatus.DUE_SOON):
            st = e.student
            due_str = e.next_payment_due.strftime("%d.%m.%Y") if e.next_payment_due else "Tez orada"
            fee_str = f"{float(e.monthly_fee):,.0f} so'm".replace(",", " ")

            # 1. O'quvchiga Telegram xabari
            if st.telegram_chat_id:
                msg = (
                    f"🔔 <b>Hurmatli {st.first_name}!</b>\n\n"
                    f"Sizning <b>{group.name}</b> guruhi bo'yicha kurs to'lov muddati: <b>{due_str}</b>.\n"
                    f"Oylik to'lov summasi: <b>{fee_str}</b>.\n\n"
                    f"Darslar to'xtab qolmasligi uchun to'lov qilib, chekni ushbu botga yuboring."
                )
                if send_telegram_message_safe(st.telegram_chat_id, msg):
                    sent_students += 1

            # 2. Ota-onaga "Shaffof Nazorat" eslatmasi
            parent_chat_id = None
            if e.parent_telegram_id and e.parent_telegram_id.isdigit():
                parent_chat_id = int(e.parent_telegram_id)
            else:
                rel = ParentStudentRelation.objects.filter(student=st, is_verified=True).first()
                if rel and rel.parent_telegram_id:
                    parent_chat_id = rel.parent_telegram_id

            if parent_chat_id:
                parent_msg = (
                    f"👨‍👩‍👧‍👦 <b>Hurmatli ota-ona! (Grand Education Shaffof Nazorat)</b>\n\n"
                    f"Farzandingiz <b>{st.get_full_name()}</b> ning <b>{group.name}</b> kursi uchun to'lov muddati: <b>{due_str}</b>.\n"
                    f"Oylik kurs to'lovi: <b>{fee_str}</b>.\n\n"
                    f"To'lovni amalga oshirgach, chekni botga yuborishingiz mumkin. Rahmat!"
                )
                if send_telegram_message_safe(parent_chat_id, parent_msg):
                    sent_parents += 1

    return Response({
        "status": "success",
        "message": f"Eslatmalar yuborildi: {sent_students} ta o'quvchiga, {sent_parents} ta ota-onaga.",
        "sent_students": sent_students,
        "sent_parents": sent_parents,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def scan_receipt_view(request):
    """
    To'lov cheki rasmini qabul qilish va Click/Payme OCR orqali tekshirish.
    POST /api/v1/payments/scan-receipt/
    """
    receipt_file = request.FILES.get("receipt")
    group_id = request.data.get("group_id")

    if not receipt_file:
        return Response({"error": "Chek rasmi ilova qilinmagan."}, status=status.HTTP_400_BAD_REQUEST)

    img_bytes = receipt_file.read()
    ocr_result = scan_receipt_image(img_bytes, filename=receipt_file.name)

    if not ocr_result.get("is_valid") or not ocr_result.get("amount"):
        return Response({
            "status": "rejected",
            "message": "To'lov cheki aniqlanmadi. Iltimos, sifatli skrinshot yuboring.",
            "ocr_result": ocr_result,
        }, status=status.HTTP_400_BAD_REQUEST)

    amount = ocr_result["amount"]
    trans_id = ocr_result["transaction_id"]

    # Agar o'quvchi guruhiga biriktirmoqchi bo'lsa
    group = None
    enrollment = None
    if group_id:
        group = get_object_or_404(StudentGroup, id=group_id)
        enrollment = GroupEnrollment.objects.filter(group=group, student=request.user).first()
    else:
        # Userning birinchi faol guruhi
        enrollment = GroupEnrollment.objects.filter(student=request.user).first()
        if enrollment:
            group = enrollment.group

    if enrollment:
        enrollment.record_payment(amount=amount)
        # Ustozga zudlik bilan bildirishnoma borishi
        if group and group.teacher and group.teacher.telegram_chat_id:
            teacher_alert = (
                f"✅ <b>Yangi to'lov cheki qabul qilindi!</b>\n\n"
                f"👤 O'quvchi: <b>{request.user.get_full_name()}</b>\n"
                f"👥 Guruh: <b>{group.name}</b>\n"
                f"💰 Summa: <b>{amount:,.0f} so'm</b>\n"
                f"🔢 Trans ID: <b>{trans_id}</b>\n"
                f"📅 Keyingi to'lov: <b>{enrollment.next_payment_due.strftime('%d.%m.%Y')}</b>"
            )
            send_telegram_message_safe(group.teacher.telegram_chat_id, teacher_alert)

    return Response({
        "status": "success",
        "message": f"Chek muvaffaqiyatli tekshirildi! To'lov summasi: {amount:,.0f} so'm.",
        "amount": amount,
        "transaction_id": trans_id,
        "provider": ocr_result.get("provider", "click"),
        "ocr_result": ocr_result,
        "next_payment_due": enrollment.next_payment_due.strftime("%Y-%m-%d") if enrollment else None,
    })
