from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.payments.models import SubscriptionPlan


class PaymentConfigurationReadinessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="billing-readiness@example.test",
            password="StrongPass123!",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        # The commercial plan catalogue is seeded by migration, so a plan type
        # may already have a row. Reuse it (with this fixture's pricing) instead
        # of assuming an empty table.
        self.paid_plan, _ = SubscriptionPlan.objects.get_or_create(
            plan_type=SubscriptionPlan.PlanType.PREMIUM,
            defaults={
                "name": "Premium",
                "description": "Paid plan",
                "price_monthly": Decimal("10000"),
            },
        )
        self.free_plan, _ = SubscriptionPlan.objects.get_or_create(
            plan_type=SubscriptionPlan.PlanType.FREE,
            defaults={
                "name": "Free",
                "description": "Free plan",
                "price_monthly": Decimal("0"),
            },
        )
        # The readiness checks depend on these prices, not on row creation.
        SubscriptionPlan.objects.filter(pk=self.paid_plan.pk).update(
            price_monthly=Decimal("10000"),
        )
        SubscriptionPlan.objects.filter(pk=self.free_plan.pk).update(
            price_monthly=Decimal("0"),
        )
        self.paid_plan.refresh_from_db()
        self.free_plan.refresh_from_db()

    @override_settings(
        PAYMENT_CARD_NUMBER="",
        PAYMENT_CARD_BANK="",
        PAYMENT_CARD_HOLDER="",
        PAYMENT_ADMIN_USERNAME="",
    )
    def test_paid_checkout_is_unavailable_without_payment_details(self):
        response = self.client.get(
            f"/api/v1/billing/subscribe/{self.paid_plan.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["payment_available"])
        self.assertFalse(response.data["free"])
        self.assertEqual(response.data["card_number"], "")
        self.assertEqual(response.data["card_bank"], "")
        self.assertEqual(response.data["card_holder"], "")
        self.assertEqual(response.data["admin_username"], "")

    @override_settings(
        PAYMENT_CARD_NUMBER="1234 5678 9012 3456",
        PAYMENT_CARD_BANK="Example Bank",
        PAYMENT_CARD_HOLDER="Example Holder",
        PAYMENT_ADMIN_USERNAME="billing-admin",
    )
    def test_configured_checkout_returns_operator_supplied_details(self):
        response = self.client.get(
            f"/api/v1/billing/subscribe/{self.paid_plan.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["payment_available"])
        self.assertEqual(response.data["card_number"], "1234 5678 9012 3456")
        self.assertEqual(response.data["card_holder"], "Example Holder")
        self.assertEqual(response.data["admin_username"], "billing-admin")

    @override_settings(
        PAYMENT_CARD_NUMBER="",
        PAYMENT_CARD_BANK="",
        PAYMENT_CARD_HOLDER="",
        PAYMENT_ADMIN_USERNAME="",
    )
    def test_free_plan_needs_no_payment_account(self):
        response = self.client.get(
            f"/api/v1/billing/subscribe/{self.free_plan.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["free"])
        self.assertTrue(response.data["payment_available"])
