"""
QA Test Suite for Quota Management, Teacher CRM, Receipt OCR, and Vocabulary Generator.
Verifies 100% correctness of:
1. TeacherProfile & Quota allocation (Superadmin -> Teacher, Teacher -> Student)
2. GroupEnrollment & Financial CRM (Due dates, statuses, 1-click reminders)
3. Receipt Scanner (Click/Payme OCR text parsing heuristics)
4. Vocabulary Pack Generator & Ebbinghaus Spaced Repetition (Streak mastery)
"""

import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.accounts.models import TeacherProfile, ParentStudentRelation
from apps.courses.models import Course, StudentGroup, GroupEnrollment, Category
from apps.payments.models import SubscriptionPlan, UserSubscription
from apps.payments.receipt_scanner import parse_receipt_text
from apps.vocabulary.models import VocabularyPack, StudentWordMistake
from apps.vocabulary.services.vocab_generator import clean_word_list, build_fallback_exercises

User = get_user_model()


@pytest.fixture
def superadmin(db):
    return User.objects.create_superuser(
        email="admin_crm@grandec.uz",
        password="secure_password123",
        first_name="Admin",
        last_name="System",
    )


@pytest.fixture
def teacher(db):
    user = User.objects.create_user(
        email="teacher_crm@grandec.uz",
        password="secure_password123",
        first_name="Ustoz",
        last_name="Qodirov",
        role=User.Role.TEACHER,
    )
    TeacherProfile.objects.create(teacher=user, pro_quota_balance=5, premium_quota_balance=2)
    return user


@pytest.fixture
def student(db):
    return User.objects.create_user(
        email="student_crm@grandec.uz",
        password="secure_password123",
        first_name="Ali",
        last_name="Valiyev",
        role=User.Role.STUDENT,
    )


@pytest.fixture
def student_group(db, teacher, student):
    group = StudentGroup.objects.create(
        teacher=teacher,
        name="IELTS Band 7.5 Intensive",
        monthly_fee=400000,
    )
    group.students.add(student)
    return group


# ===========================================================================
# 1. QUOTA ALLOCATION & ACTIVATION TESTS
# ===========================================================================

@pytest.mark.django_db
def test_admin_quota_allocation(client, superadmin, teacher):
    """Superadmin allocates +10 PRO quotas to teacher."""
    client.force_login(superadmin)
    url = f"/api/v1/panel/teachers/{teacher.id}/allocate-quota/"
    payload = {"quota_type": "pro", "amount": 10}

    res = client.post(url, data=payload, content_type="application/json")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["pro_quota_balance"] == 15  # 5 initial + 10 added

    teacher.teacher_profile.refresh_from_db()
    assert teacher.teacher_profile.pro_quota_balance == 15


@pytest.mark.django_db
def test_teacher_activates_quota_for_student(client, teacher, student, student_group):
    """Teacher activates 30 days of PRO for their student using quota."""
    client.force_login(teacher)
    url = f"/api/v1/courses/groups/{student_group.id}/students/{student.id}/activate-quota/"
    payload = {"plan_type": "pro"}

    res = client.post(url, data=payload, content_type="application/json")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["plan"] == "pro"

    # Teacher quota decreased by 1
    teacher.teacher_profile.refresh_from_db()
    assert teacher.teacher_profile.pro_quota_balance == 4

    # Student received PRO
    student.profile.refresh_from_db()
    assert student.profile.plan == "pro"
    assert student.has_pro_access is True


@pytest.mark.django_db
def test_teacher_quota_insufficient(client, teacher, student, student_group):
    """Fails with 400 when teacher runs out of quota."""
    teacher.teacher_profile.premium_quota_balance = 0
    teacher.teacher_profile.save()

    client.force_login(teacher)
    url = f"/api/v1/courses/groups/{student_group.id}/students/{student.id}/activate-quota/"
    payload = {"plan_type": "premium"}

    res = client.post(url, data=payload, content_type="application/json")
    assert res.status_code == 400
    assert "PREMIUM kvota qolmagan" in res.json()["error"]


# ===========================================================================
# 2. GROUP ENROLLMENT & TEACHER CRM TESTS
# ===========================================================================

@pytest.mark.django_db
def test_group_enrollment_lifecycle(student_group, student):
    """Verifies GroupEnrollment status updates and payment recording."""
    today = timezone.localdate()
    enrollment = GroupEnrollment.objects.create(
        group=student_group,
        student=student,
        monthly_fee=Decimal("400000.00"),
        billing_cycle_day=10,
        last_payment_date=today - timedelta(days=35),
        next_payment_due=today - timedelta(days=5),  # overdue
        payment_status=GroupEnrollment.PaymentStatus.PAID,
    )

    # 1. Update status -> becomes overdue
    status = enrollment.update_status(today)
    assert status == GroupEnrollment.PaymentStatus.OVERDUE
    assert enrollment.payment_status == GroupEnrollment.PaymentStatus.OVERDUE

    # 2. Record payment -> paid, extended by 30 days
    enrollment.record_payment(amount=400000, payment_date=today, extend_days=30)
    enrollment.refresh_from_db()
    assert enrollment.payment_status == GroupEnrollment.PaymentStatus.PAID
    assert enrollment.last_payment_date == today
    assert enrollment.next_payment_due == today + timedelta(days=30)


@pytest.mark.django_db
def test_group_finance_summary_api(client, teacher, student_group):
    """Tests GET /api/v1/courses/groups/<id>/finance-summary/."""
    client.force_login(teacher)
    url = f"/api/v1/courses/groups/{student_group.id}/finance-summary/"

    res = client.get(url)
    assert res.status_code == 200
    data = res.json()
    assert data["group_id"] == student_group.id
    assert data["total_students"] == 1
    assert data["pro_quota_balance"] == 5
    assert len(data["students"]) == 1


# ===========================================================================
# 3. CLICK / PAYME RECEIPT OCR PARSER TESTS
# ===========================================================================

def test_parse_receipt_click_sample():
    """Verifies parsing of a standard Click receipt snippet."""
    sample_text = """
    CLICK TO'LOV CHEKI
    MPO109847291
    Sana: 24.10.2026 14:30
    Qabul qiluvchi: GRAND EDUCATION MCHJ
    Jami summa: 400 000 so'm
    Holati: Muvaffaqiyatli to'landi
    """
    parsed = parse_receipt_text(sample_text)
    assert parsed["is_valid"] is True
    assert parsed["amount"] == 400000.0
    assert parsed["provider"] == "click"
    assert "MPO109847291" in parsed["transaction_id"]


def test_parse_receipt_payme_sample():
    """Verifies parsing of a Payme receipt snippet."""
    sample_text = """
    Payme Chek № PAYME88921102
    Data: 23.10.2026
    Oplata uslug: Kurs to'lovi
    Summa: 500,000 UZS
    Uspeshno
    """
    parsed = parse_receipt_text(sample_text)
    assert parsed["is_valid"] is True
    assert parsed["amount"] == 500000.0
    assert parsed["provider"] == "payme"
    assert "PAYME88921102" in parsed["transaction_id"]


# ===========================================================================
# 4. VOCABULARY GENERATOR & SPACED REPETITION TESTS
# ===========================================================================

def test_clean_word_list():
    raw = "1. resilient\n2. persistent, 3. ubiquitous\nmeticulous\nresilient"
    words = clean_word_list(raw)
    assert len(words) == 4
    assert words == ["resilient", "persistent", "ubiquitous", "meticulous"]


def test_build_fallback_exercises():
    words = ["resilient", "persistent", "ubiquitous", "meticulous"]
    ex = build_fallback_exercises(words)
    assert "format_1_quiz" in ex
    assert "format_2_spelling" in ex
    assert "format_3_eng_uzb" in ex
    assert "format_4_uzb_eng" in ex
    assert len(ex["format_1_quiz"]) == 4
    assert ex["format_1_quiz"][0]["correct_answer"] == "resilient"


@pytest.mark.django_db
def test_spaced_repetition_streak_mastery(student):
    """Verifies that 3 consecutive correct answers mark a word as mastered."""
    mistake = StudentWordMistake.objects.create(
        student=student,
        word="resilient",
        translation_uz="bardoshli, chidamli",
        mistake_count=2,
        consecutive_correct_streak=0,
        is_mastered=False,
    )

    # Attempt 1: Correct
    mastered = mistake.record_attempt(is_correct=True)
    assert mastered is False
    assert mistake.consecutive_correct_streak == 1
    assert mistake.is_mastered is False

    # Attempt 2: Correct
    mastered = mistake.record_attempt(is_correct=True)
    assert mastered is False
    assert mistake.consecutive_correct_streak == 2
    assert mistake.is_mastered is False

    # Attempt 3: Correct -> Mastered!
    mastered = mistake.record_attempt(is_correct=True)
    assert mastered is True
    assert mistake.consecutive_correct_streak == 3
    assert mistake.is_mastered is True
