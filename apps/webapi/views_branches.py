"""
Educational Center (Filial / Kursxona), Teachers & Group Management Views.
Provides APIs for:
1. Panel Branch Management (/api/v1/panel/branches/)
2. Panel Teacher Management & Assignment (/api/v1/panel/teachers/)
3. Student & Public Branches Catalog (/api/v1/school/branches/catalog/)
4. Student Group View with Live Leaderboard & Assigned Tests (/api/v1/school/groups/<id>/student-view/)
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import models
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.access import is_platform_admin
from apps.accounts.models import Profile, User
from apps.courses.group_service import get_group_full_analytics
from apps.courses.models import StudentGroup
from apps.organizations.models import CenterBranch, LearningCenter
from apps.results.models import Result
from apps.tests.models import Test, TestAttempt

from .permissions import IsPanelAdmin

logger = logging.getLogger(__name__)


def _can_manage_branches(user: User) -> bool:
    return bool(
        user.is_authenticated
        and (
            is_platform_admin(user)
            or user.is_staff
            or user.is_superuser
            or user.role in ("admin", "center_admin")
        )
    )


# ============================================================================
# 1. Panel Branch Management
# ============================================================================
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def panel_branches_list_create_view(request):
    """
    GET: List all educational center branches (Kursxonalar) with metrics.
    POST: Create a new branch with director, limits, and subjects.
    """
    if not _can_manage_branches(request.user):
        return Response({"detail": "Ushbu amalni bajarish uchun ruxsat yo'q."}, status=403)

    if request.method == "POST":
        data = request.data
        name = str(data.get("name", "")).strip()
        if not name:
            return Response({"error": "Filial nomi kiritilishi shart."}, status=400)

        branch_code = str(data.get("branch_code", "")).strip().upper()
        if branch_code and CenterBranch.objects.filter(branch_code=branch_code).exists():
            return Response({"error": f"'{branch_code}' kodi allaqachon mavjud."}, status=400)

        region = str(data.get("region", "")).strip()
        address = str(data.get("address", "")).strip()
        phone = str(data.get("phone", "")).strip()
        telegram_channel = str(data.get("telegram_channel", "")).strip()
        subjects_offered = data.get("subjects_offered")
        if not subjects_offered or not isinstance(subjects_offered, list):
            subjects_offered = ["biology", "chemistry", "law", "uzbek", "english"]

        max_teachers = int(data.get("max_teachers_limit", 20) or 20)
        max_students = int(data.get("max_students_limit", 500) or 500)

        director_id = data.get("director_id")
        director = None
        if director_id:
            director = User.objects.filter(id=director_id).first()
            if director and director.role != "admin":
                director.role = "center_admin"
                director.save(update_fields=["role"])

        center = LearningCenter.objects.first()

        branch = CenterBranch.objects.create(
            center=center,
            name=name,
            branch_code=branch_code,
            region=region,
            address=address,
            phone=phone,
            telegram_channel=telegram_channel,
            director=director,
            subjects_offered=subjects_offered,
            max_teachers_limit=max_teachers,
            max_students_limit=max_students,
            is_active=True,
        )

        return Response(
            {
                "success": True,
                "message": f"'{branch.name}' filiali muvaffaqiyatli yaratildi.",
                "branch": _serialize_branch(branch),
            },
            status=status.HTTP_201_CREATED,
        )

    # GET
    branches = CenterBranch.objects.filter(is_active=True).order_by("-created_at")
    results = [_serialize_branch(b) for b in branches]
    return Response(results)


@api_view(["GET", "PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def panel_branch_detail_view(request, branch_id: int):
    """
    Branch detail, update, and deletion/deactivation.
    """
    if not _can_manage_branches(request.user):
        return Response({"detail": "Ruxsat etilmagan."}, status=403)

    branch = get_object_or_404(CenterBranch, id=branch_id)

    if request.method == "DELETE":
        branch.is_active = False
        branch.save(update_fields=["is_active"])
        return Response({"success": True, "message": "Filial faolsizlantirildi."})

    if request.method in ("PATCH", "PUT"):
        data = request.data
        if "name" in data and str(data["name"]).strip():
            branch.name = str(data["name"]).strip()
        if "branch_code" in data and str(data["branch_code"]).strip():
            code = str(data["branch_code"]).strip().upper()
            if CenterBranch.objects.filter(branch_code=code).exclude(id=branch.id).exists():
                return Response({"error": f"'{code}' kodi boshqa filialda mavjud."}, status=400)
            branch.branch_code = code
        if "region" in data:
            branch.region = str(data["region"]).strip()
        if "address" in data:
            branch.address = str(data["address"]).strip()
        if "phone" in data:
            branch.phone = str(data["phone"]).strip()
        if "telegram_channel" in data:
            branch.telegram_channel = str(data["telegram_channel"]).strip()
        if "subjects_offered" in data and isinstance(data["subjects_offered"], list):
            branch.subjects_offered = data["subjects_offered"]
        if "max_teachers_limit" in data:
            branch.max_teachers_limit = int(data["max_teachers_limit"])
        if "max_students_limit" in data:
            branch.max_students_limit = int(data["max_students_limit"])
        if "director_id" in data:
            did = data["director_id"]
            branch.director = User.objects.filter(id=did).first() if did else None
            if branch.director and branch.director.role != "admin":
                branch.director.role = "center_admin"
                branch.director.save(update_fields=["role"])

        branch.save()
        return Response(
            {
                "success": True,
                "message": "Filial ma'lumotlari yangilandi.",
                "branch": _serialize_branch(branch, include_relations=True),
            }
        )

    return Response(_serialize_branch(branch, include_relations=True))


def _serialize_branch(branch: CenterBranch, include_relations: bool = False) -> dict[str, Any]:
    director_data = None
    if branch.director:
        director_data = {
            "id": branch.director.id,
            "name": branch.director.get_full_name() or branch.director.email,
            "email": branch.director.email,
            "phone": getattr(getattr(branch.director, "profile", None), "phone", ""),
        }

    data: dict[str, Any] = {
        "id": branch.id,
        "name": branch.name,
        "slug": branch.slug,
        "branch_code": branch.branch_code,
        "region": branch.region,
        "address": branch.address,
        "phone": branch.phone,
        "telegram_channel": branch.telegram_channel,
        "director": director_data,
        "subjects_offered": branch.subjects_offered or [],
        "max_teachers_limit": branch.max_teachers_limit,
        "max_students_limit": branch.max_students_limit,
        "is_active": branch.is_active,
        "teachers_count": branch.teachers_count,
        "students_count": branch.students_count,
        "groups_count": branch.groups_count,
        "avg_performance": branch.avg_performance,
        "created_at": branch.created_at.isoformat() if branch.created_at else None,
    }

    if include_relations:
        teachers = branch.users.filter(role="teacher", is_active=True).select_related("profile")
        data["teachers"] = [
            {
                "id": t.id,
                "name": t.get_full_name() or t.email,
                "email": t.email,
                "phone": getattr(getattr(t, "profile", None), "phone", ""),
                "subject": getattr(getattr(t, "profile", None), "active_subject", "uzbek"),
                "groups_count": t.managed_groups.count(),
            }
            for t in teachers
        ]
        groups = branch.groups.all().select_related("teacher")
        data["groups"] = [
            {
                "id": g.id,
                "name": g.name,
                "subject": g.subject,
                "invite_code": g.invite_code,
                "teacher_name": g.teacher.get_full_name() or g.teacher.email,
                "student_count": g.students.count(),
            }
            for g in groups
        ]

    return data


# ============================================================================
# 2. Panel Teachers Management & Assignment
# ============================================================================
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def panel_teachers_view(request):
    """
    GET: List all teachers with their branch, subject, groups, and permissions.
    POST: Assign or update teacher's branch, subject, and test/essay permissions.
    """
    if not _can_manage_branches(request.user):
        return Response({"detail": "Ruxsat etilmagan."}, status=403)

    if request.method == "POST":
        data = request.data
        teacher_id = data.get("teacher_id")
        teacher = None

        if teacher_id:
            teacher = get_object_or_404(User, id=teacher_id)
        else:
            email = str(data.get("email", "")).strip().lower()
            if not email:
                return Response({"error": "Ustoz emaili kiritilmadi."}, status=400)
            teacher = User.objects.filter(email=email).first()
            if not teacher:
                raw_pwd = str(data.get("password", "")).strip() or "GrandTeacher2026!"
                name = str(data.get("name", "")).strip() or email.split("@")[0]
                first_name = name.split()[0] if name else "Ustoz"
                last_name = " ".join(name.split()[1:]) if len(name.split()) > 1 else ""
                teacher = User.objects.create_user(
                    email=email,
                    password=raw_pwd,
                    first_name=first_name,
                    last_name=last_name,
                    role="teacher",
                    is_active=True,
                )
                Profile.objects.get_or_create(user=teacher)

        teacher.role = "teacher"

        branch_id = data.get("branch_id")
        if branch_id is not None:
            if branch_id == "" or branch_id == 0:
                teacher.branch = None
            else:
                branch = get_object_or_404(CenterBranch, id=branch_id)
                teacher.branch = branch
                if branch.center:
                    teacher.learning_center = branch.center

        if "can_create_test" in data:
            teacher.can_create_test = bool(data["can_create_test"])
        else:
            teacher.can_create_test = True

        if "can_create_essay_topic" in data:
            teacher.can_create_essay_topic = bool(data["can_create_essay_topic"])

        if "is_active" in data:
            teacher.is_active = bool(data["is_active"])

        teacher.save()

        # Update subject in Profile
        subject = str(data.get("subject", "")).strip().lower()
        if subject in ("biology", "chemistry", "law", "uzbek", "english"):
            prof, _ = Profile.objects.get_or_create(user=teacher)
            prof.active_subject = subject
            if "phone" in data and str(data["phone"]).strip():
                prof.phone = str(data["phone"]).strip()
            prof.save(update_fields=["active_subject", "phone"] if "phone" in data else ["active_subject"])

        return Response(
            {
                "success": True,
                "message": f"Ustoz {teacher.get_full_name()} sozlamalari saqlandi.",
                "teacher": _serialize_teacher(teacher),
            }
        )

    # GET
    teachers = (
        User.objects.filter(Q(role="teacher") | Q(managed_groups__isnull=False))
        .distinct()
        .select_related("branch", "profile")
        .prefetch_related("managed_groups__students")
        .order_by("-date_joined")
    )
    teacher_items = [_serialize_teacher(t) for t in teachers]
    branches = [
        {"id": b.id, "name": b.name, "branch_code": b.branch_code, "region": b.region}
        for b in CenterBranch.objects.filter(is_active=True).order_by("name")
    ]
    return Response({
        "results": teacher_items,
        "branches": branches,
        "total": len(teacher_items),
    })


def _serialize_teacher(teacher: User) -> dict[str, Any]:
    prof = getattr(teacher, "profile", None)
    groups = teacher.managed_groups.all()
    all_students_ids = set()
    for g in groups:
        for s in g.students.all():
            all_students_ids.add(s.id)

    branch_info = None
    if teacher.branch:
        branch_info = {
            "id": teacher.branch.id,
            "name": teacher.branch.name,
            "branch_code": teacher.branch.branch_code,
            "region": teacher.branch.region,
        }

    return {
        "id": teacher.id,
        "name": teacher.get_full_name() or teacher.email,
        "email": teacher.email,
        "phone": getattr(prof, "phone", "") or "",
        "role": teacher.role,
        "branch": branch_info,
        "subject": getattr(prof, "active_subject", "uzbek") or "uzbek",
        "can_create_test": teacher.can_create_test,
        "can_create_essay_topic": teacher.can_create_essay_topic,
        "is_active": teacher.is_active,
        "groups_count": groups.count(),
        "students_count": len(all_students_ids),
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "subject": g.subject,
                "invite_code": g.invite_code,
                "student_count": g.students.count(),
            }
            for g in groups
        ],
        "date_joined": teacher.date_joined.isoformat() if teacher.date_joined else None,
    }


# ============================================================================
# 3. Student & Public Branches Catalog
# ============================================================================
@api_view(["GET"])
@permission_classes([AllowAny])
def school_branches_catalog_view(request):
    """
    Public / Student catalog: Active branches with subjects, teachers, and open groups.
    """
    branches = (
        CenterBranch.objects.filter(is_active=True)
        .prefetch_related("groups__teacher", "groups__students")
        .order_by("name")
    )

    result = []
    for b in branches:
        groups_list = []
        for g in b.groups.all():
            groups_list.append(
                {
                    "id": g.id,
                    "name": g.name,
                    "subject": g.subject,
                    "subject_display": g.get_subject_display() if hasattr(g, "get_subject_display") else g.subject,
                    "teacher_name": g.teacher.get_full_name() or g.teacher.email,
                    "teacher_phone": getattr(getattr(g.teacher, "profile", None), "phone", ""),
                    "student_count": g.students.count(),
                    "invite_code": g.invite_code,
                    "invite_token": g.invite_token,
                }
            )

        result.append(
            {
                "id": b.id,
                "name": b.name,
                "branch_code": b.branch_code,
                "region": b.region,
                "address": b.address,
                "phone": b.phone,
                "telegram_channel": b.telegram_channel,
                "subjects_offered": b.subjects_offered or [],
                "groups": groups_list,
            }
        )

    return Response(result)


# ============================================================================
# 4. Student Group View (Live Leaderboard, Assigned Tests, Group Context)
# ============================================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def student_group_detail_view(request, group_id: int):
    """
    GET /api/v1/school/groups/<group_id>/student-view/
    Returns full interactive group environment:
      - Branch & Teacher info
      - Assigned homework tests (with student completion state)
      - Live Group Leaderboard (🥇 🥈 🥉 medals, BMB grade, avg percentage)
    """
    group = get_object_or_404(StudentGroup, id=group_id)
    user = request.user

    is_teacher = (group.teacher == user)
    is_admin = is_platform_admin(user)
    is_member = group.students.filter(id=user.id).exists()

    if not (is_teacher or is_admin or is_member):
        return Response(
            {"detail": "Siz bu guruh a'zosi emassiz. Avval guruhga qo'shiling."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # 1. Branch info
    branch_info = None
    if group.branch:
        branch_info = {
            "id": group.branch.id,
            "name": group.branch.name,
            "branch_code": group.branch.branch_code,
            "region": group.branch.region,
            "address": group.branch.address,
            "phone": group.branch.phone,
            "telegram_channel": group.branch.telegram_channel,
        }

    # 2. Teacher info
    teacher_prof = getattr(group.teacher, "profile", None)
    subject_label_map = {
        "biology": "🧬 Biologiya",
        "chemistry": "🧪 Kimyo",
        "law": "⚖️ Huquqshunoslik",
        "uzbek": "🇺🇿 Ona tili va Adabiyot",
        "english": "🇬🇧 Ingliz tili",
    }
    teacher_subject = getattr(teacher_prof, "active_subject", group.subject) or group.subject
    teacher_info = {
        "id": group.teacher.id,
        "name": group.teacher.get_full_name() or group.teacher.email,
        "email": group.teacher.email,
        "phone": getattr(teacher_prof, "phone", "") or "",
        "subject": teacher_subject,
        "subject_label": subject_label_map.get(teacher_subject, teacher_subject.capitalize()),
        "qualification": "Oliy toifali ustoz / Mutaxassis",
    }

    # 3. Assigned Tests
    # Either explicitly assigned to this group or active tests created by group's teacher
    assigned_tests_qs = (
        Test.objects.filter(Q(assigned_group=group) | Q(created_by=group.teacher, subject=group.subject))
        .filter(is_active=True)
        .distinct()
        .order_by("-created_at")[:10]
    )

    tests_data = []
    for test in assigned_tests_qs:
        # Check student result
        user_res = (
            Result.objects.filter(test=test, student=user)
            .order_by("-calculated_at")
            .first()
        )
        user_att = (
            TestAttempt.objects.filter(test=test, student=user, completed_at__isnull=True)
            .order_by("-started_at")
            .first()
        )

        test_state = "not_started"
        if user_res:
            test_state = "completed"
        elif user_att:
            test_state = "in_progress"

        tests_data.append(
            {
                "id": test.id,
                "title": test.title,
                "subject": test.subject,
                "total_questions": test.questions.count(),
                "duration_minutes": getattr(test, "time_limit_minutes", 60),
                "passing_score": getattr(test, "passing_score", 60),
                "status": test_state,
                "result": (
                    {
                        "score": user_res.score,
                        "max_score": user_res.max_score,
                        "percentage": float(user_res.percentage),
                        "grade": user_res.grade,
                        "date": user_res.calculated_at.strftime("%d.%m.%Y"),
                    }
                    if user_res
                    else None
                ),
                "attempt_id": user_att.id if user_att else (user_res.attempt_id if user_res else None),
            }
        )

    # 4. Live Group Leaderboard
    analytics = get_group_full_analytics(group)
    raw_students = analytics.get("students", [])

    leaderboard = []
    my_rank = None
    for item in raw_students:
        rank = item.get("rank", 1)
        medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else None))
        is_me = (item.get("student_id") == user.id)
        if is_me:
            my_rank = rank

        leaderboard.append(
            {
                "rank": rank,
                "medal": medal,
                "student_id": item.get("student_id"),
                "student_name": item.get("student_name") or item.get("full_name"),
                "email": item.get("email"),
                "avg_test_pct": item.get("avg_test_pct", 0.0),
                "tests_taken": item.get("tests_taken", 0),
                "bmb_grade": item.get("bmb_grade", "—"),
                "essays_written": item.get("essays_written", 0),
                "last_active": item.get("last_active", "Yaqinda"),
                "is_me": is_me,
            }
        )

    return Response(
        {
            "group": {
                "id": group.id,
                "name": group.name,
                "subject": group.subject,
                "subject_display": group.get_subject_display() if hasattr(group, "get_subject_display") else group.subject,
                "description": group.description or "",
                "invite_code": group.invite_code,
                "invite_token": group.invite_token,
                "student_count": group.students.count(),
                "created_at": group.created_at.isoformat() if group.created_at else None,
            },
            "branch": branch_info,
            "teacher": teacher_info,
            "assigned_tests": tests_data,
            "leaderboard": leaderboard,
            "my_rank": my_rank,
            "is_teacher": is_teacher,
            "is_admin": is_admin,
        }
    )
