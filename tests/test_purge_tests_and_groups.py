from decimal import Decimal
import io
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.courses.models import Course
from apps.essays.models import EssaySubmission, EssayTopic
from apps.groups.models import StudentGroup
from apps.payments.models import PaymentReceipt, SubscriptionPlan, UserSubscription
from apps.tests.models import Choice, Question, Test

User = get_user_model()


@pytest.mark.django_db
def test_purge_tests_and_groups_dry_run():
    # Setup test and group data
    user = User.objects.create_user(
        email="testuser1@example.com",
        password="passPassword123!",
        first_name="Test",
        role="teacher",
    )
    course = Course.objects.create(teacher=user, title="Test Course 1", slug="test-course-1")
    test_obj = Test.objects.create(course=course, title="Sample Test 1", subject="math")
    q = Question.objects.create(test=test_obj, text="2+2=?")
    Choice.objects.create(question=q, text="4", is_correct=True)
    StudentGroup.objects.create(name="Group A", teacher=user)

    out = io.StringIO()
    call_command("purge_tests_and_groups", "--dry-run", stdout=out)
    output = out.getvalue()

    assert "[DRY RUN]" in output
    # Check that data was NOT deleted
    assert Test.objects.count() == 1
    assert Question.objects.count() == 1
    assert Choice.objects.count() == 1
    assert StudentGroup.objects.count() == 1
    assert User.objects.filter(email="testuser1@example.com").exists()


@pytest.mark.django_db
def test_purge_tests_and_groups_confirm_and_preserve_protected():
    user = User.objects.create_user(
        email="testuser2@example.com",
        password="passPassword123!",
        first_name="Test2",
        role="teacher",
    )
    plan, _ = SubscriptionPlan.objects.get_or_create(
        plan_type=SubscriptionPlan.PlanType.PRO,
        defaults={"name": "Pro Plan", "price_monthly": Decimal("60000")},
    )
    UserSubscription.objects.create(user=user, plan=plan)
    receipt = PaymentReceipt.objects.create(
        user=user,
        amount=Decimal("60000"),
        plan="pro",
    )

    topic = EssayTopic.objects.create(title="Sample Essay Topic", description="Write about literature.")
    EssaySubmission.objects.create(
        student=user,
        topic=topic,
        essay_text="Sample essay content for testing preservation.",
    )

    course = Course.objects.create(teacher=user, title="Test Course 2", slug="test-course-2")
    test_obj = Test.objects.create(course=course, title="Test to Delete", subject="native_language")
    q = Question.objects.create(test=test_obj, text="Alisher Navoiy qachon tug'ilgan?")
    Choice.objects.create(question=q, text="1441", is_correct=True)
    StudentGroup.objects.create(name="Group to Delete", teacher=user)

    out = io.StringIO()
    call_command("purge_tests_and_groups", "--confirm", stdout=out)
    output = out.getvalue()

    assert "[OK] Barcha eski testlar, urinishlar va guruhlar muvaffaqiyatli tozalandi!" in output

    # Check purged
    assert Test.objects.count() == 0
    assert Question.objects.count() == 0
    assert Choice.objects.count() == 0
    assert StudentGroup.objects.count() == 0

    # Check preserved
    assert User.objects.filter(email="testuser2@example.com").exists()
    assert UserSubscription.objects.filter(user=user).exists()
    assert PaymentReceipt.objects.filter(id=receipt.id).exists()
    assert EssayTopic.objects.filter(title="Sample Essay Topic").exists()
    assert EssaySubmission.objects.filter(student=user).exists()
