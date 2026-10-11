"""Teacher-sponsored free access.

The security-critical property under test is that a teacher **cannot**
self-grant a free entitlement: a group membership alone is never sufficient,
and an administrator approval (``approved_at``) is what makes the sponsorship
effective. Removal/revocation must never destroy the student's own account,
essays or independently purchased subscription.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import StudentGroup
from apps.payments.entitlements import (
    SOURCE_DEFAULT,
    SOURCE_SPONSORED,
    SOURCE_SUBSCRIPTION,
    get_effective_entitlement,
    get_remaining_limits,
)
from apps.payments.models import (
    SubscriptionPlan,
    TeacherSponsorship,
    UserSubscription,
)


def make_plan(plan_type: str, **overrides) -> SubscriptionPlan:
    """Fetch or create a plan row and pin the fields this test depends on."""
    defaults = {
        "name": plan_type.upper(),
        "description": "",
        "price_monthly": 0,
        "price_yearly": 0,
        "image_essay_weekly_limit": None,
        "text_essay_weekly_limit": None,
        "text_essay_cooldown_hours": None,
        "test_limit": None,
        "is_unlimited_image_essays": False,
        "is_unlimited_text_essays": False,
        "is_unlimited_tests": False,
        "duration_days": 30,
        "quota_period_days": 7,
        "telegram_stars_price": None,
        "is_public": False,
        "is_active": True,
    }
    defaults.update(overrides)
    plan, _created = SubscriptionPlan.objects.get_or_create(
        plan_type=plan_type, defaults=defaults,
    )
    for field, value in defaults.items():
        setattr(plan, field, value)
    plan.save()
    return plan


class _SponsorshipFixture(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="sponsor-admin@example.test",
            password="StrongPass123!",
            role="admin",
        )
        self.teacher = User.objects.create_user(
            email="sponsor-teacher@example.test",
            password="StrongPass123!",
            role="teacher",
        )
        self.student = User.objects.create_user(
            email="sponsor-student@example.test",
            password="StrongPass123!",
            role="student",
        )
        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.student)
        self.sponsored_plan = make_plan(
            "teacher_sponsored",
            image_essay_weekly_limit=5,
            text_essay_weekly_limit=3,
            text_essay_cooldown_hours=5,
            is_public=False,
        )

    def approve(self, **overrides) -> TeacherSponsorship:
        defaults = {
            "student": self.student,
            "group": self.group,
            "is_active": True,
            "approved_at": timezone.now(),
            "approved_by": self.admin,
        }
        defaults.update(overrides)
        return TeacherSponsorship.objects.create(**defaults)

    def paid_subscription(self, *, plan_type: str = "start", days: int = 30):
        plan = make_plan(plan_type, is_public=True)
        return UserSubscription.objects.create(
            user=self.student,
            plan=plan,
            status=UserSubscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=days),
        )


class SponsorshipGrantTests(_SponsorshipFixture):
    def test_group_membership_alone_grants_nothing(self):
        """Being in a teacher's group is necessary but never sufficient."""
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_DEFAULT)
        self.assertFalse(entitlement.is_sponsored)

    def test_teacher_created_but_unapproved_sponsorship_grants_nothing(self):
        """Anti self-grant: without administrator approval there is no access."""
        self.approve(approved_at=None, approved_by=None)
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_DEFAULT)
        self.assertFalse(entitlement.is_sponsored)
        self.assertNotEqual(entitlement.plan_type, "teacher_sponsored")

    def test_approved_group_member_receives_sponsored_entitlement(self):
        self.approve()
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_SPONSORED)
        self.assertTrue(entitlement.is_sponsored)
        self.assertEqual(entitlement.plan_type, "teacher_sponsored")
        self.assertEqual(entitlement.image_essay_weekly_limit, 5)
        self.assertEqual(entitlement.text_essay_weekly_limit, 3)
        self.assertEqual(entitlement.text_essay_cooldown_hours, 5)
        self.assertFalse(entitlement.is_paid)

        remaining = get_remaining_limits(self.student)
        self.assertTrue(remaining["is_sponsored"])
        self.assertEqual(remaining["plan_name"], self.sponsored_plan.name)

    def test_sponsorship_does_not_create_a_subscription_row(self):
        """Sponsored access is an entitlement source, not a paid subscription."""
        self.approve()
        self.assertEqual(UserSubscription.objects.filter(user=self.student).count(), 0)
        self.assertEqual(get_effective_entitlement(self.student).source, SOURCE_SPONSORED)

    def test_student_must_still_be_a_member_of_the_group(self):
        self.approve()
        self.assertEqual(get_effective_entitlement(self.student).source, SOURCE_SPONSORED)

        self.group.students.remove(self.student)
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_DEFAULT)
        self.assertFalse(entitlement.is_sponsored)

    def test_expired_sponsorship_is_ignored(self):
        self.approve(expires_at=timezone.now() - timedelta(minutes=1))
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_DEFAULT)

    def test_inactive_sponsorship_is_ignored(self):
        self.approve(is_active=False)
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_DEFAULT)

    def test_is_effective_property_matches_resolution(self):
        active = self.approve()
        self.assertTrue(active.is_effective)
        self.assertTrue(get_effective_entitlement(self.student).is_sponsored)

        # A second group's sponsorship that an administrator has not approved
        # yet must not be effective (nor conflict with the approved one).
        pending_group = StudentGroup.objects.create(
            teacher=self.teacher, name="11-C",
        )
        pending_group.students.add(self.student)
        pending = TeacherSponsorship.objects.create(
            student=self.student, group=pending_group, is_active=True,
        )
        self.assertFalse(pending.is_effective)

    def test_expired_approval_does_not_make_a_sponsorship_effective(self):
        sponsorship = self.approve(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(sponsorship.is_effective)
        self.assertFalse(get_effective_entitlement(self.student).is_sponsored)

    def test_sponsorship_is_scoped_to_the_approved_student(self):
        self.approve()
        other = User.objects.create_user(
            email="sponsor-other@example.test", password="StrongPass123!",
            role="student",
        )
        self.group.students.add(other)
        self.assertEqual(
            get_effective_entitlement(other).source, SOURCE_DEFAULT,
        )


class SponsorshipOverrideTests(_SponsorshipFixture):
    def test_group_overrides_are_applied_on_top_of_the_sponsored_plan(self):
        self.approve(image_essay_weekly_limit=10, text_essay_weekly_limit=None,
                     is_unlimited_text_essays=True)
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_SPONSORED)
        self.assertEqual(entitlement.image_essay_weekly_limit, 10)
        self.assertTrue(entitlement.is_unlimited_text_essays)

    def test_sponsorship_can_grant_unlimited_tests(self):
        self.approve(is_unlimited_tests=True)
        entitlement = get_effective_entitlement(self.student)
        self.assertTrue(entitlement.is_unlimited_tests)
        self.assertFalse(entitlement.is_unlimited_image_essays)

    def test_explicit_zero_override_is_honoured(self):
        """0 is a real value: an administrator can explicitly deny a category."""
        self.approve(image_essay_weekly_limit=0)
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.image_essay_weekly_limit, 0)
        self.assertNotEqual(entitlement.image_essay_weekly_limit, None)


class SponsorshipPrecedenceTests(_SponsorshipFixture):
    def test_sponsorship_outranks_a_paid_subscription(self):
        self.paid_subscription()
        self.approve()
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_SPONSORED)

    def test_revoking_sponsorship_keeps_the_independent_paid_subscription(self):
        subscription = self.paid_subscription()
        sponsorship = self.approve()
        self.assertEqual(get_effective_entitlement(self.student).source, SOURCE_SPONSORED)

        sponsorship.is_active = False
        sponsorship.revoked_at = timezone.now()
        sponsorship.save(update_fields=["is_active", "revoked_at", "updated_at"])

        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_SUBSCRIPTION)
        subscription.refresh_from_db()
        self.assertTrue(subscription.is_active)
        self.assertEqual(subscription.plan_id, subscription.plan_id)

    def test_revoking_sponsorship_leaves_a_sponsorless_student_on_default(self):
        sponsorship = self.approve()
        self.assertEqual(get_effective_entitlement(self.student).source, SOURCE_SPONSORED)
        sponsorship.is_active = False
        sponsorship.save(update_fields=["is_active", "updated_at"])
        self.assertEqual(get_effective_entitlement(self.student).source, SOURCE_DEFAULT)

    def test_missing_sponsored_plan_row_falls_through_to_the_next_tier(self):
        """A sponsorship without a configured plan cannot be honoured."""
        self.sponsored_plan.is_active = False
        self.sponsored_plan.save(update_fields=["is_active", "updated_at"])
        self.approve()
        self.paid_subscription()
        entitlement = get_effective_entitlement(self.student)
        self.assertEqual(entitlement.source, SOURCE_SUBSCRIPTION)
        self.assertFalse(entitlement.is_sponsored)

    def test_two_approved_groups_do_not_duplicate_entitlements(self):
        second_group = StudentGroup.objects.create(teacher=self.teacher, name="10-B")
        second_group.students.add(self.student)
        self.approve()
        TeacherSponsorship.objects.create(
            student=self.student,
            group=second_group,
            is_active=True,
            approved_at=timezone.now(),
            approved_by=self.admin,
        )
        self.assertEqual(
            TeacherSponsorship.objects.filter(
                student=self.student, is_active=True,
            ).count(),
            2,
        )
        # Still exactly one entitlement, and no duplicate subscription rows.
        self.assertEqual(get_effective_entitlement(self.student).source, SOURCE_SPONSORED)
        self.assertEqual(UserSubscription.objects.filter(user=self.student).count(), 0)

    def test_active_sponsorship_per_group_is_unique(self):
        from django.db import IntegrityError, transaction

        self.approve()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.approve()
