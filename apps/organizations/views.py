"""
Views for B2B SaaS Enterprise Learning Center Hub.
"""
from __future__ import annotations

import csv
import io
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg, Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Profile
from apps.organizations.models import CenterBranch, LearningCenter
from apps.results.models import Result

User = get_user_model()


def _get_user_center(user) -> LearningCenter | None:
    """Find the learning center owned by or linked to the user."""
    if hasattr(user, "owned_centers") and user.owned_centers.exists():
        return user.owned_centers.first()
    if getattr(user, "learning_center", None):
        return user.learning_center
    if user.is_staff or user.role == "admin":
        return LearningCenter.objects.first()
    return None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def enterprise_dashboard_view(request):
    """
    Direktor va Menejer Kabineti:
    - Umumiy statistika (Jami o'quvchilar, bugun test ishlaganlar, o'rtacha BMB).
    - Ustozlar reytingi.
    - Filiallararo raqobat statistikasi.
    """
    user = request.user
    center = _get_user_center(user)

    # If user doesn't have a center yet, auto-provision one for demo/owner
    if not center:
        center = LearningCenter.objects.create(
            name=f"{user.get_full_name() or user.first_name or 'Grand'} Ta'lim Markazi",
            owner=user,
            student_seat_limit=100,
            subscription_expires_at=timezone.now() + timedelta(days=365),
        )
        CenterBranch.objects.create(center=center, name="Bosh filial")
        user.learning_center = center
        user.save(update_fields=["learning_center"])

    students = center.users.filter(role="student")
    total_students = students.count()
    seat_limit = center.student_seat_limit

    today = timezone.now().date()
    active_today = Result.objects.filter(
        student__in=students,
        calculated_at__date=today,
    ).values("student").distinct().count()

    results_qs = Result.objects.filter(student__in=students)
    avg_score = results_qs.aggregate(avg=Avg("percentage"))["avg"] or 0.0

    # Calculate BMB Grade
    if avg_score >= 86:
        bmb_grade = "A+ (A'lo)"
    elif avg_score >= 80:
        bmb_grade = "A (A'lo)"
    elif avg_score >= 73:
        bmb_grade = "B+ (Yaxshi)"
    elif avg_score >= 67:
        bmb_grade = "B (Yaxshi)"
    elif avg_score >= 60:
        bmb_grade = "C+ (Qoniqarli)"
    elif avg_score >= 53:
        bmb_grade = "C (Qoniqarli)"
    else:
        bmb_grade = "Boshlang'ich"

    # Branch Competition stats
    branches_data = []
    for branch in center.branches.all():
        b_students = students.filter(branch=branch)
        b_count = b_students.count()
        b_avg = Result.objects.filter(student__in=b_students).aggregate(avg=Avg("percentage"))["avg"] or 0.0
        branches_data.append({
            "id": branch.id,
            "name": branch.name,
            "students_count": b_count,
            "avg_score": round(float(b_avg), 1),
            "phone": branch.phone,
        })
    branches_data.sort(key=lambda x: x["avg_score"], reverse=True)

    # Teachers ranking
    teachers = center.users.filter(role="teacher")
    teachers_data = []
    for t in teachers:
        # Teachers might have groups or assigned students
        t_students = students.filter(branch=t.branch) if t.branch else students
        t_avg = Result.objects.filter(student__in=t_students).aggregate(avg=Avg("percentage"))["avg"] or 0.0
        teachers_data.append({
            "id": t.id,
            "name": t.get_full_name() or t.email,
            "email": t.email,
            "students_count": t_students.count(),
            "avg_score": round(float(t_avg), 1),
            "branch_name": t.branch.name if t.branch else "Umumiy",
        })
    teachers_data.sort(key=lambda x: x["avg_score"], reverse=True)

    # Recent results
    recent_results = []
    for r in results_qs.select_related("student", "test").order_by("-calculated_at")[:8]:
        recent_results.append({
            "id": r.id,
            "student_name": r.student.get_full_name(),
            "test_title": r.test.title,
            "percentage": float(r.percentage),
            "is_passed": r.is_passed,
            "created_at": r.calculated_at,
        })

    return Response({
        "center": {
            "id": center.id,
            "name": center.name,
            "slug": center.slug,
            "student_seat_limit": seat_limit,
            "remaining_seats": center.remaining_seats,
            "subscription_expires_at": center.subscription_expires_at,
            "is_active": center.is_active,
        },
        "stats": {
            "total_students": total_students,
            "seat_limit": seat_limit,
            "active_today": active_today,
            "avg_score": round(float(avg_score), 1),
            "bmb_grade": bmb_grade,
        },
        "branches": branches_data,
        "teachers": teachers_data,
        "recent_results": recent_results,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def enterprise_bulk_import_view(request):
    """
    O'quvchilarni ommaviy yuklash (Bulk Import via CSV / Excel / JSON).
    Bir vaqtning o'zida 500 tagacha o'quvchini bazaga kiritish.
    """
    center = _get_user_center(request.user)
    if not center:
        return Response({"error": "Sizda o'quv markazi biriktirilmagan."}, status=status.HTTP_400_BAD_REQUEST)

    students_payload = request.data.get("students")
    csv_file = request.FILES.get("file")

    rows_to_import = []

    if csv_file:
        try:
            decoded = csv_file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(decoded))
            for row in reader:
                rows_to_import.append({
                    "first_name": row.get("first_name") or row.get("ism") or "O'quvchi",
                    "last_name": row.get("last_name") or row.get("familiya") or "",
                    "email": row.get("email") or "",
                    "phone": row.get("phone") or row.get("telefon") or "",
                    "branch_name": row.get("branch") or row.get("filial") or "",
                })
        except Exception as e:
            return Response({"error": f"CSV faylni o'qishda xatolik: {e}"}, status=status.HTTP_400_BAD_REQUEST)
    elif isinstance(students_payload, list):
        rows_to_import = students_payload

    if not rows_to_import:
        return Response(
            {"error": "Yuklash uchun o'quvchilar ro'yxati yoki CSV fayl topilmadi."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check seat limit
    current_count = center.total_students_count
    remaining = center.student_seat_limit - current_count
    if len(rows_to_import) > remaining:
        return Response(
            {
                "error": f"Markazingizdagi bo'sh o'rinlar soni: {remaining} ta. "
                f"Siz {len(rows_to_import)} ta o'quvchi yuklamoqchisiz. "
                f"Iltimos, tarifingizni kengaytiring."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    imported_count = 0
    skipped_count = 0

    with transaction.atomic():
        for r in rows_to_import[:500]:
            first_name = str(r.get("first_name", "")).strip() or "O'quvchi"
            last_name = str(r.get("last_name", "")).strip()
            raw_email = str(r.get("email", "")).strip().lower()
            phone = str(r.get("phone", "")).strip()
            branch_name = str(r.get("branch_name", "")).strip()

            if not raw_email:
                # generate unique email if not provided
                import uuid
                clean_phone = "".join(filter(str.isdigit, phone)) or uuid.uuid4().hex[:6]
                raw_email = f"student_{clean_phone}@grandec.uz"

            branch = None
            if branch_name:
                branch, _ = CenterBranch.objects.get_or_create(
                    center=center,
                    name=branch_name,
                )
            elif center.branches.exists():
                branch = center.branches.first()

            user_obj, created = User.objects.get_or_create(
                email=raw_email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": "student",
                    "learning_center": center,
                    "branch": branch,
                },
            )
            if created:
                user_obj.set_password("Grand2026!")
                user_obj.save()
                Profile.objects.get_or_create(user=user_obj, defaults={"phone": phone})
                imported_count += 1
            else:
                # Update center association if unassigned
                if not user_obj.learning_center:
                    user_obj.learning_center = center
                    user_obj.branch = branch
                    user_obj.save(update_fields=["learning_center", "branch"])
                    imported_count += 1
                else:
                    skipped_count += 1

    return Response({
        "success": True,
        "imported": imported_count,
        "skipped": skipped_count,
        "total_students": center.total_students_count,
        "message": f"{imported_count} ta o'quvchi muvaffaqiyatli markazga qo'shildi! Standart parol: Grand2026!",
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def enterprise_report_export_view(request):
    """
    Markaz logotipi va imzosi tushirilgan umumiy oylik tahliliy hisobotni eksport qilish.
    """
    center = _get_user_center(request.user)
    if not center:
        return Response({"error": "Markaz topilmadi."}, status=status.HTTP_404_NOT_FOUND)

    students = center.users.filter(role="student")
    results = Result.objects.filter(student__in=students).select_related("student", "test")

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="{center.slug}_monthly_report.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "GRAND EDUCATION — B2B ENTERPRISE MONITORING HISOBOTI",
        f"Markaz: {center.name}",
        f"Sana: {timezone.now().strftime('%Y-%m-%d %H:%M')}",
    ])
    writer.writerow([])
    writer.writerow(["№", "O'quvchi", "Filial", "Test", "Ball", "Foiz", "Natija", "Sana"])

    for idx, r in enumerate(results.order_by("-calculated_at")[:1000], start=1):
        branch_name = r.student.branch.name if r.student.branch else "—"
        writer.writerow([
            idx,
            r.student.get_full_name(),
            branch_name,
            r.test.title,
            r.score,
            f"{r.percentage}%",
            "O'tdi" if r.is_passed else "O'tmadi",
            r.calculated_at.strftime("%Y-%m-%d %H:%M") if r.calculated_at else "",
        ])

    return response
