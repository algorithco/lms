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

from django.db import transaction
from django.db.models import Avg, Count, OuterRef, Prefetch, Q, QuerySet, Subquery
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Profile, User
from apps.courses.group_service import get_group_full_analytics
from apps.courses.models import StudentGroup
from apps.organizations.models import CenterBranch, LearningCenter
from apps.results.models import Result
from apps.tests.models import Test, TestAttempt

logger = logging.getLogger(__name__)

SUBJECT_SLUGS = ("biology", "chemistry", "law", "uzbek", "english")
DEFAULT_TEACHER_LIMIT = 20
DEFAULT_STUDENT_LIMIT = 500
MAX_LIMIT_VALUE = 100_000


# ============================================================================
# Access control (tenant isolation)
# ============================================================================
def _is_global_admin(user: User) -> bool:
    """Platform-wide administrator: may manage EVERY branch and assign directors.

    ``is_staff`` alone is intentionally not enough (see apps.accounts.access).
    """
    return bool(
        user.is_authenticated
        and user.is_active
        and (user.is_superuser or user.role == User.Role.ADMIN)
    )


def _is_branch_admin(user: User) -> bool:
    return bool(
        user.is_authenticated and user.is_active and user.role == User.Role.CENTER_ADMIN
    )


def _can_manage_branches(user: User) -> bool:
    """Entry gate for the panel: global admin or a (scoped) center admin."""
    return _is_global_admin(user) or _is_branch_admin(user)


def _manageable_branches(user: User) -> QuerySet[CenterBranch]:
    """
    Branches the user may read/modify.

    * global admin  -> all branches
    * center_admin  -> only branches they direct, their own branch, or
                       branches of a learning center they own
    * everyone else -> none
    """
    if _is_global_admin(user):
        return CenterBranch.objects.all()
    if _is_branch_admin(user):
        scope = Q(director=user) | Q(center__owner=user)
        if user.branch_id:
            scope |= Q(pk=user.branch_id)
        return CenterBranch.objects.filter(scope).distinct()
    return CenterBranch.objects.none()


def _can_manage_branch(user: User, branch: CenterBranch | None) -> bool:
    if branch is None:
        return False
    if _is_global_admin(user):
        return True
    return _manageable_branches(user).filter(pk=branch.pk).exists()


def _forbidden() -> Response:
    return Response({"detail": "Ushbu amalni bajarish uchun ruxsat yo'q."}, status=403)


def _parse_limit(value: Any, default: int) -> int:
    """Parse a user supplied limit into a safe non-negative int (ValueError -> 400)."""
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Limit butun son bo'lishi kerak.") from exc
    if number < 0 or number > MAX_LIMIT_VALUE:
        raise ValueError(f"Limit 0 dan {MAX_LIMIT_VALUE} gacha bo'lishi kerak.")
    return number


def _clean_subjects(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    cleaned = [str(v).strip().lower() for v in value if str(v).strip().lower() in SUBJECT_SLUGS]
    return list(dict.fromkeys(cleaned)) or None


def _assign_director(director_id: Any) -> tuple[User | None, Response | None]:
    """
    Resolve a branch director. Only global admins reach this (callers check).
    Privileged accounts keep their role; ordinary users are promoted to center_admin.
    """
    if not director_id:
        return None, None
    director = User.objects.filter(id=director_id, is_active=True).first()
    if director is None:
        return None, Response({"error": "Direktor topilmadi."}, status=400)
    if director.is_superuser or director.role == User.Role.ADMIN:
        return director, None
    if director.role != User.Role.CENTER_ADMIN:
        director.role = User.Role.CENTER_ADMIN
        director.save(update_fields=["role"])
    return director, None


def _branches_with_stats(qs: QuerySet[CenterBranch]) -> QuerySet[CenterBranch]:
    """
    Annotate every branch with its metrics so serialisation needs NO extra queries
    (replaces the per-branch ``teachers_count`` / ``students_count`` /
    ``groups_count`` / ``avg_performance`` property queries).
    """
    avg_perf = (
        Result.objects.filter(student__branch=OuterRef("pk"), student__role="student")
        .order_by()
        .values("student__branch")
        .annotate(avg=Avg("percentage"))
        .values("avg")
    )
    return qs.select_related("director", "director__profile", "center").annotate(
        stat_teachers=Count(
            "users", filter=Q(users__role="teacher", users__is_active=True), distinct=True
        ),
        stat_students=Count(
            "users", filter=Q(users__role="student", users__is_active=True), distinct=True
        ),
        stat_groups=Count("groups", distinct=True),
        stat_avg=Subquery(avg_perf),
    )


# ============================================================================
# 1. Panel Branch Management
# ============================================================================
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def panel_branches_list_create_view(request):
    """
    GET: List the branches (Kursxonalar) the user may manage, with metrics.
    POST: Create a new branch (global admin only).
    """
    if not _can_manage_branches(request.user):
        return _forbidden()

    if request.method == "POST":
        # Creating branches (and appointing directors) is a platform-level action:
        # a center admin must not be able to spawn branches inside another tenant.
        if not _is_global_admin(request.user):
            return _forbidden()

        data = request.data
        name = str(data.get("name", "")).strip()
        if not name:
            return Response({"error": "Filial nomi kiritilishi shart."}, status=400)

        branch_code = str(data.get("branch_code", "")).strip().upper()
        if branch_code and CenterBranch.objects.filter(branch_code=branch_code).exists():
            return Response({"error": f"'{branch_code}' kodi allaqachon mavjud."}, status=400)

        try:
            max_teachers = _parse_limit(data.get("max_teachers_limit"), DEFAULT_TEACHER_LIMIT)
            max_students = _parse_limit(data.get("max_students_limit"), DEFAULT_STUDENT_LIMIT)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        subjects_offered = _clean_subjects(data.get("subjects_offered")) or list(SUBJECT_SLUGS)

        center_id = data.get("center_id")
        if center_id:
            center = LearningCenter.objects.filter(id=center_id).first()
            if center is None:
                return Response({"error": "O'quv markazi topilmadi."}, status=400)
        else:
            center = LearningCenter.objects.first()

        with transaction.atomic():
            director, err = _assign_director(data.get("director_id"))
            if err is not None:
                return err

            branch = CenterBranch.objects.create(
                center=center,
                name=name,
                branch_code=branch_code or None,
                region=str(data.get("region", "")).strip(),
                address=str(data.get("address", "")).strip(),
                phone=str(data.get("phone", "")).strip(),
                telegram_channel=str(data.get("telegram_channel", "")).strip(),
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
    branches = _branches_with_stats(
        _manageable_branches(request.user).filter(is_active=True)
    ).order_by("-created_at")
    return Response([_serialize_branch(b) for b in branches])


@api_view(["GET", "PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def panel_branch_detail_view(request, branch_id: int):
    """
    Branch detail, update, and deactivation.

    The lookup is scoped to the caller's manageable branches, so another
    tenant's branch id answers 404 (no IDOR, no existence leak).
    """
    if not _can_manage_branches(request.user):
        return _forbidden()

    branch = get_object_or_404(_manageable_branches(request.user), id=branch_id)
    is_global = _is_global_admin(request.user)

    if request.method == "DELETE":
        if not is_global:
            return _forbidden()
        branch.is_active = False
        branch.save(update_fields=["is_active"])
        return Response({"success": True, "message": "Filial faolsizlantirildi."})

    if request.method in ("PATCH", "PUT"):
        data = request.data
        # Fields that change tenancy, billing limits or privileges are platform-only.
        platform_only = {"branch_code", "max_teachers_limit", "max_students_limit", "director_id"}
        if not is_global and platform_only.intersection(data.keys()):
            return Response(
                {"detail": "Bu maydonlarni faqat platforma administratori o'zgartira oladi."},
                status=403,
            )

        try:
            new_teacher_limit = (
                _parse_limit(data["max_teachers_limit"], branch.max_teachers_limit)
                if "max_teachers_limit" in data
                else None
            )
            new_student_limit = (
                _parse_limit(data["max_students_limit"], branch.max_students_limit)
                if "max_students_limit" in data
                else None
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        new_code = None
        if "branch_code" in data and str(data["branch_code"]).strip():
            new_code = str(data["branch_code"]).strip().upper()
            if CenterBranch.objects.filter(branch_code=new_code).exclude(id=branch.id).exists():
                return Response({"error": f"'{new_code}' kodi boshqa filialda mavjud."}, status=400)

        with transaction.atomic():
            if "director_id" in data:
                director, err = _assign_director(data["director_id"])
                if err is not None:
                    return err
                branch.director = director
            if "name" in data and str(data["name"]).strip():
                branch.name = str(data["name"]).strip()
            if new_code:
                branch.branch_code = new_code
            for field in ("region", "address", "phone", "telegram_channel"):
                if field in data:
                    setattr(branch, field, str(data[field]).strip())
            if "subjects_offered" in data:
                subjects = _clean_subjects(data["subjects_offered"])
                if subjects:
                    branch.subjects_offered = subjects
            if new_teacher_limit is not None:
                branch.max_teachers_limit = new_teacher_limit
            if new_student_limit is not None:
                branch.max_students_limit = new_student_limit
            branch.save()

        branch = _branches_with_stats(CenterBranch.objects.filter(pk=branch.pk)).get()
        return Response(
            {
                "success": True,
                "message": "Filial ma'lumotlari yangilandi.",
                "branch": _serialize_branch(branch, include_relations=True),
            }
        )

    branch = _branches_with_stats(CenterBranch.objects.filter(pk=branch.pk)).get()
    return Response(_serialize_branch(branch, include_relations=True))


def _serialize_branch(branch: CenterBranch, include_relations: bool = False) -> dict[str, Any]:
    director = branch.director
    director_data = None
    if director:
        director_data = {
            "id": director.id,
            "name": director.get_full_name() or director.email,
            "email": director.email,
            "phone": getattr(getattr(director, "profile", None), "phone", ""),
        }

    # Prefer the annotated metrics (zero extra queries); fall back to the model
    # properties for freshly created, un-annotated instances.
    has_stats = hasattr(branch, "stat_groups")
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
        "teachers_count": branch.stat_teachers if has_stats else branch.teachers_count,
        "students_count": branch.stat_students if has_stats else branch.students_count,
        "groups_count": branch.stat_groups if has_stats else branch.groups_count,
        "avg_performance": (
            round(float(branch.stat_avg or 0.0), 1) if has_stats else branch.avg_performance
        ),
        "created_at": branch.created_at.isoformat() if branch.created_at else None,
    }

    if include_relations:
        teachers = (
            branch.users.filter(role="teacher", is_active=True)
            .select_related("profile")
            .annotate(stat_groups=Count("managed_groups", distinct=True))
        )
        data["teachers"] = [
            {
                "id": t.id,
                "name": t.get_full_name() or t.email,
                "email": t.email,
                "phone": getattr(getattr(t, "profile", None), "phone", ""),
                "subject": getattr(getattr(t, "profile", None), "active_subject", "uzbek"),
                "groups_count": t.stat_groups,
            }
            for t in teachers
        ]
        groups = branch.groups.select_related("teacher").annotate(stat_students=Count("students"))
        data["groups"] = [
            {
                "id": g.id,
                "name": g.name,
                "subject": g.subject,
                "invite_code": g.invite_code,
                "teacher_name": g.teacher.get_full_name() or g.teacher.email,
                "student_count": g.stat_students,
            }
            for g in groups
        ]

    return data


# ============================================================================
# 2. Panel Teachers Management & Assignment
# ============================================================================
def _is_privileged_account(user: User) -> bool:
    return bool(user.is_superuser or user.role in (User.Role.ADMIN, User.Role.CENTER_ADMIN))


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def panel_teachers_view(request):
    """
    GET: List teachers (scoped to the caller's branches) with branch, subject, groups, permissions.
    POST: Assign or update a teacher's branch, subject, and test/essay permissions.

    A center admin can only touch teachers of THEIR branches and can only place
    teachers into THEIR branches. Privileged accounts (admin / center_admin /
    superuser) can never be reassigned or demoted through this endpoint.
    """
    user = request.user
    if not _can_manage_branches(user):
        return _forbidden()

    is_global = _is_global_admin(user)
    scope_ids: set[int] | None = (
        None if is_global else set(_manageable_branches(user).values_list("id", flat=True))
    )

    if request.method == "POST":
        return _assign_teacher(request, is_global=is_global, scope_ids=scope_ids)

    # GET
    teacher_filter = Q(role="teacher") | Q(managed_groups__isnull=False)
    if is_global:
        # Platform admins can also lead groups, so they stay assignable (legacy contract).
        teacher_filter |= Q(role="admin") | Q(is_superuser=True)
    teachers = User.objects.filter(teacher_filter)
    if scope_ids is not None:
        teachers = teachers.filter(branch_id__in=scope_ids)
    teachers = (
        teachers.distinct()
        .select_related("branch", "profile")
        .prefetch_related("managed_groups__students")
        .order_by("-date_joined")
    )
    teacher_items = [_serialize_teacher(t) for t in teachers]
    branches = [
        {"id": b.id, "name": b.name, "branch_code": b.branch_code, "region": b.region}
        for b in _manageable_branches(user).filter(is_active=True).order_by("name")
    ]
    return Response({
        "results": teacher_items,
        "branches": branches,
        "total": len(teacher_items),
    })


def _assign_teacher(request, *, is_global: bool, scope_ids: set[int] | None) -> Response:
    data = request.data
    teacher_id = data.get("teacher_id")
    temp_password: str | None = None

    # Resolve the target branch first (and check the caller may place people there).
    branch_id = data.get("branch_id")
    target_branch: CenterBranch | None = None
    unassign = branch_id is not None and branch_id in ("", 0, "0")
    if branch_id is not None and not unassign:
        target_branch = get_object_or_404(CenterBranch, id=branch_id)
        if not is_global and target_branch.id not in (scope_ids or set()):
            return Response({"detail": "Bu filialga ustoz biriktirishga ruxsatingiz yo'q."}, status=403)

    with transaction.atomic():
        if teacher_id:
            teacher = get_object_or_404(User, id=teacher_id)
        else:
            email = str(data.get("email", "")).strip().lower()
            if not email:
                return Response({"error": "Ustoz emaili kiritilmadi."}, status=400)
            teacher = User.objects.filter(email=email).first()
            if teacher is None:
                if not is_global and target_branch is None:
                    return Response({"error": "Yangi ustoz uchun filial (branch_id) ko'rsatilishi shart."}, status=400)
                raw_pwd = str(data.get("password", "")).strip()
                if raw_pwd:
                    from django.contrib.auth.password_validation import validate_password
                    from django.core.exceptions import ValidationError as DjangoValidationError

                    try:
                        validate_password(raw_pwd)
                    except DjangoValidationError as exc:
                        return Response({"error": " ".join(exc.messages)}, status=400)
                else:
                    # Never fall back to a shared/default password.
                    raw_pwd = get_random_string(14)
                    temp_password = raw_pwd
                name = str(data.get("name", "")).strip() or email.split("@")[0]
                parts = name.split()
                teacher = User.objects.create_user(
                    email=email,
                    password=raw_pwd,
                    first_name=parts[0] if parts else "Ustoz",
                    last_name=" ".join(parts[1:]),
                    role="teacher",
                    is_active=True,
                )
                Profile.objects.get_or_create(user=teacher)

        # Privileged accounts must never be demoted / re-homed through this endpoint.
        if _is_privileged_account(teacher):
            return Response({"detail": "Administrator hisobini ustoz sifatida o'zgartirib bo'lmaydi."}, status=403)

        if not is_global:
            in_scope = teacher.branch_id in (scope_ids or set())
            unassigned_teacher = teacher.branch_id is None and teacher.role == "teacher"
            if not (in_scope or unassigned_teacher):
                # Hide the existence of users from other tenants.
                return Response({"detail": "Ustoz topilmadi."}, status=404)

        teacher.role = "teacher"

        if unassign:
            teacher.branch = None
        elif target_branch is not None and teacher.branch_id != target_branch.id:
            current = target_branch.users.filter(role="teacher", is_active=True).exclude(pk=teacher.pk).count()
            if current >= target_branch.max_teachers_limit:
                return Response(
                    {"error": f"Filialda ustozlar limiti to'lgan ({target_branch.max_teachers_limit})."},
                    status=400,
                )
            teacher.branch = target_branch
            if target_branch.center_id:
                teacher.learning_center_id = target_branch.center_id

        if "can_create_test" in data:
            teacher.can_create_test = bool(data["can_create_test"])
        else:
            teacher.can_create_test = True

        if "can_create_essay_topic" in data:
            teacher.can_create_essay_topic = bool(data["can_create_essay_topic"])

        if "is_active" in data:
            teacher.is_active = bool(data["is_active"])

        teacher.save()

        subject = str(data.get("subject", "")).strip().lower()
        if subject in SUBJECT_SLUGS:
            prof, _ = Profile.objects.get_or_create(user=teacher)
            prof.active_subject = subject
            fields = ["active_subject"]
            phone = str(data.get("phone", "")).strip()
            if phone:
                prof.phone = phone
                fields.append("phone")
            prof.save(update_fields=fields)

    payload: dict[str, Any] = {
        "success": True,
        "message": f"Ustoz {teacher.get_full_name()} sozlamalari saqlandi.",
        "teacher": _serialize_teacher(teacher),
    }
    if temp_password:
        # Shown once to the admin who created the account; never stored in clear text.
        payload["temporary_password"] = temp_password
    return Response(payload)


def _serialize_teacher(teacher: User) -> dict[str, Any]:
    prof = getattr(teacher, "profile", None)
    # Uses the prefetched managed_groups / students when available (list view).
    groups = list(teacher.managed_groups.all())
    group_students = {g.id: list(g.students.all()) for g in groups}
    all_students_ids = {s.id for students in group_students.values() for s in students}

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
        "full_name": teacher.get_full_name() or teacher.email,
        "email": teacher.email,
        "phone": getattr(prof, "phone", "") or "",
        "role": teacher.role,
        "branch": branch_info,
        "subject": getattr(prof, "active_subject", "uzbek") or "uzbek",
        "can_create_test": teacher.can_create_test,
        "can_create_essay_topic": teacher.can_create_essay_topic,
        "is_active": teacher.is_active,
        "groups_count": len(groups),
        "students_count": len(all_students_ids),
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "subject": g.subject,
                "invite_code": g.invite_code,
                "student_count": len(group_students[g.id]),
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

    Public response deliberately omits the secret ``invite_token`` and the
    teacher's phone number (shown to signed-in users only).
    """
    is_authed = bool(request.user and request.user.is_authenticated)
    groups_qs = StudentGroup.objects.select_related("teacher", "teacher__profile").annotate(
        stat_students=Count("students")
    )
    branches = (
        CenterBranch.objects.filter(is_active=True)
        .prefetch_related(Prefetch("groups", queryset=groups_qs))
        .order_by("name")
    )

    result = []
    for b in branches:
        groups_list = []
        for g in b.groups.all():
            item: dict[str, Any] = {
                "id": g.id,
                "name": g.name,
                "subject": g.subject,
                "subject_display": g.get_subject_display(),
                "teacher_name": g.teacher.get_full_name() or g.teacher.email,
                "student_count": g.stat_students,
                "invite_code": g.invite_code,
            }
            if is_authed:
                item["teacher_phone"] = getattr(getattr(g.teacher, "profile", None), "phone", "")
            groups_list.append(item)

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

    Access: the group's teacher, its members, a platform admin, or a center
    admin of the group's own branch. Student e-mails are visible to staff only.
    """
    group = get_object_or_404(
        StudentGroup.objects.select_related("branch", "teacher", "teacher__profile"),
        id=group_id,
    )
    user = request.user

    is_teacher = group.teacher_id == user.id
    is_admin = _is_global_admin(user) or (
        _is_branch_admin(user) and _can_manage_branch(user, group.branch)
    )
    is_member = group.students.filter(id=user.id).exists()

    if not (is_teacher or is_admin or is_member):
        return Response(
            {"detail": "Siz bu guruh a'zosi emassiz. Avval guruhga qo'shiling."},
            status=status.HTTP_403_FORBIDDEN,
        )
    can_see_emails = is_teacher or is_admin

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
        "email": group.teacher.email if can_see_emails or is_member else "",
        "phone": getattr(teacher_prof, "phone", "") or "",
        "subject": teacher_subject,
        "subject_label": subject_label_map.get(teacher_subject, teacher_subject.capitalize()),
        "qualification": "Oliy toifali ustoz / Mutaxassis",
    }

    # 3. Assigned tests: ONE query for tests (+question counts), ONE for the
    # student's results and ONE for open attempts (was 2-3 queries per test).
    assigned_tests = list(
        Test.objects.filter(Q(assigned_group=group) | Q(created_by=group.teacher, subject=group.subject))
        .filter(is_active=True)
        .distinct()
        .annotate(stat_questions=Count("questions", distinct=True))
        .order_by("-created_at")[:10]
    )
    test_ids = [t.id for t in assigned_tests]

    latest_result: dict[int, Result] = {}
    for res in Result.objects.filter(test_id__in=test_ids, student=user).order_by("test_id", "-calculated_at"):
        latest_result.setdefault(res.test_id, res)

    open_attempt: dict[int, TestAttempt] = {}
    for att in TestAttempt.objects.filter(
        test_id__in=test_ids, student=user, completed_at__isnull=True
    ).order_by("test_id", "-started_at"):
        open_attempt.setdefault(att.test_id, att)

    tests_data = []
    for test in assigned_tests:
        user_res = latest_result.get(test.id)
        user_att = open_attempt.get(test.id)

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
                "total_questions": test.stat_questions,
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

    # 4. Live Group Leaderboard (aggregated in the service: 4 queries total)
    analytics = get_group_full_analytics(group)
    raw_students = analytics.get("students", [])

    leaderboard = []
    my_rank = None
    for item in raw_students:
        rank = item.get("rank", 1)
        medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else None))
        is_me = item.get("student_id") == user.id
        if is_me:
            my_rank = rank

        leaderboard.append(
            {
                "rank": rank,
                "medal": medal,
                "student_id": item.get("student_id"),
                "student_name": item.get("student_name") or item.get("full_name"),
                # Classmates' e-mail addresses are PII: staff only (own e-mail is fine).
                "email": item.get("email") if (can_see_emails or is_me) else None,
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
                "subject_display": group.get_subject_display(),
                "description": group.description or "",
                "invite_code": group.invite_code,
                "invite_token": group.invite_token if can_see_emails else None,
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
