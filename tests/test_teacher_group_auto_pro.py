import pytest
from django.contrib.auth import get_user_model
from apps.courses.models import StudentGroup
from apps.courses.group_service import join_group_by_invite_code, get_group_full_analytics
from apps.payments.models import SubscriptionPlan
from apps.payments.entitlements import get_effective_entitlement
from apps.payments.ai_quota import get_user_plan_tier
from apps.accounts.serializers import RegisterSerializer

User = get_user_model()


@pytest.mark.django_db
def test_teacher_registration_permissions():
    """Ustoz ro'yxatdan o'tganda avtomatik guruh va test yaratish huquqlari beriladi."""
    data = {
        "email": "teacher_test@grandec.uz",
        "first_name": "Alisher",
        "last_name": "Ustoz",
        "password": "StrongPassword123!",
        "password_confirm": "StrongPassword123!",
        "role": "teacher",
    }
    serializer = RegisterSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    user = serializer.save()

    assert user.role == User.Role.TEACHER
    assert user.can_create_test is True
    assert user.can_create_essay_topic is True
    assert user.has_pro_access is True


@pytest.mark.django_db
def test_student_auto_pro_on_group_join():
    """O'quvchi guruh taklif kodini kiritib qo'shilganda avtomatik PRO tarifiga ega bo'ladi."""
    # Ensure PRO plan exists in DB
    SubscriptionPlan.objects.get_or_create(
        plan_type=SubscriptionPlan.PlanType.PRO,
        defaults={"name": "PRO", "price_monthly": 49000, "is_active": True},
    )

    teacher = User.objects.create_user(
        email="lead_teacher@grandec.uz",
        password="TeacherPass123!",
        role=User.Role.TEACHER,
        first_name="Ustoz",
        last_name="Grand",
    )

    group = StudentGroup.objects.create(
        teacher=teacher,
        name="Ona tili Intensive",
        invite_code="GR-INT99",
    )

    student = User.objects.create_user(
        email="student_pro_test@grandec.uz",
        password="StudentPass123!",
        role=User.Role.STUDENT,
        first_name="Temur",
        last_name="O'quvchi",
    )

    # Initial state: student has no group and is not PRO
    assert student.student_groups.count() == 0
    assert student.profile.plan in ("free", "")

    # Student joins via invite code (with or without #)
    joined_group = join_group_by_invite_code(student, "#GR-INT99")
    assert joined_group.id == group.id
    assert group.students.filter(id=student.id).exists()

    # Re-fetch student to verify PRO status
    student.refresh_from_db()
    assert student.has_pro_access is True
    assert student.profile.plan == "pro"

    # Effective entitlement must be sponsored
    ent = get_effective_entitlement(student)
    assert ent.plan_name in ("PRO (Ustoz guruhi orqali)", "Ustoz guruhi (homiylik)", "Ustoz homiyligi", "PRO")
    assert ent.is_sponsored is True
    assert ent.is_unlimited_tests is True

    # AI Quota tier must be "pro" (50 requests/day)
    tier = get_user_plan_tier(student)
    assert tier == "pro"

    # Group analytics must report PRO status
    analytics = get_group_full_analytics(group)
    assert analytics["total_students"] == 1
    student_metric = analytics["students"][0]
    assert student_metric["student_id"] == student.id
    assert student_metric["has_pro"] is True
    assert student_metric["pro_status_label"] == "⭐ PRO (Faol)"
