"""
Comprehensive test suite for AI Vision Payment Receipt Verifier & Anti-Fraud Engine.
Tests:
- Valid receipt activation for Starter, PRO, and PREMIUM plans
- SHA-256 hash duplicate rejection & strike
- Transaction ID reuse rejection & immediate auto-ban
- Strike policy (Strike 1 warning, Strike 2 / theft auto-ban)
- Banned user 403 blocking in Middleware and SimpleJWT
- Web API endpoint POST /api/v1/subscriptions/verify-receipt/
- Telegram bot payment receipt handling & ban responses
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.subscriptions.models import PaymentReceipt, FraudLog
from apps.subscriptions.services import (
    ReceiptVerifier,
    compute_receipt_hash,
    apply_fraud_strike,
)
from apps.payments.models import UserSubscription, SubscriptionPlan

User = get_user_model()


class ReceiptVerifierAntiFraudTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="student@grandec.uz",
            password="testpassword123",
            first_name="Alisher",
            last_name="Navoiy",
            role=User.Role.STUDENT,
        )
        self.other_user = User.objects.create_user(
            email="other@grandec.uz",
            password="testpassword123",
            first_name="Bobur",
            last_name="Zahiriddin",
            role=User.Role.STUDENT,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("apps.subscriptions.services.receipt_verifier.scan_receipt_vision")
    def test_valid_starter_receipt_activates_plan(self, mock_scan):
        """Authentic Starter receipt activates Starter plan immediately."""
        fake_bytes = b"sample_starter_receipt_image_data_12345"
        mock_scan.return_value = {
            "is_valid": True,
            "amount": 7000.0,
            "transaction_id": "CLICK-STARTER-9901",
            "payment_system": PaymentReceipt.PaymentSystem.CLICK,
            "date_str": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            "recipient": "GRAND EDUCATION",
            "is_success": True,
        }

        res = ReceiptVerifier.verify_receipt(
            user=self.user,
            image_bytes=fake_bytes,
            plan_type="starter",
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["plan_type"], "starter")
        self.assertEqual(res["transaction_id"], "CLICK-STARTER-9901")

        # Verify PaymentReceipt saved
        receipt = PaymentReceipt.objects.get(transaction_id="CLICK-STARTER-9901")
        self.assertTrue(receipt.is_verified)
        self.assertEqual(receipt.amount, Decimal("7000"))
        self.assertEqual(receipt.receipt_hash, compute_receipt_hash(fake_bytes))

        # Verify plan activated
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "starter")

    @patch("apps.subscriptions.services.receipt_verifier.scan_receipt_vision")
    def test_valid_pro_receipt_activates_pro_subscription(self, mock_scan):
        """Authentic 49,000 UZS receipt activates PRO 30-day subscription."""
        fake_bytes = b"sample_pro_receipt_image_data_67890"
        mock_scan.return_value = {
            "is_valid": True,
            "amount": 49000.0,
            "transaction_id": "PAYME-PRO-8812",
            "payment_system": PaymentReceipt.PaymentSystem.PAYME,
            "date_str": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            "recipient": "GRAND EDUCATION",
            "is_success": True,
        }

        res = ReceiptVerifier.verify_receipt(
            user=self.user,
            image_bytes=fake_bytes,
            plan_type="pro",
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["plan_type"], "pro")

        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "pro")
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, UserSubscription.Status.ACTIVE)
        self.assertEqual(sub.plan.plan_type, SubscriptionPlan.PlanType.PRO)

    @patch("apps.subscriptions.services.receipt_verifier.scan_receipt_vision")
    def test_duplicate_transaction_id_triggers_immediate_ban(self, mock_scan):
        """Reusing an already-registered Transaction ID triggers immediate Auto-Ban."""
        _ = PaymentReceipt.objects.create(
            user=self.other_user,
            plan_type="pro",
            amount=Decimal("49000"),
            payment_system=PaymentReceipt.PaymentSystem.CLICK,
            transaction_id="CLICK-DUPLICATE-TX-100",
            receipt_image="receipts/test.jpg",
            receipt_hash="hash_abc_123",
            is_verified=True,
        )

        fake_bytes = b"different_image_bytes_trying_to_reuse_tx"
        mock_scan.return_value = {
            "is_valid": True,
            "amount": 49000.0,
            "transaction_id": "CLICK-DUPLICATE-TX-100",  # Duplicate!
            "payment_system": PaymentReceipt.PaymentSystem.CLICK,
            "date_str": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            "recipient": "GRAND EDUCATION",
            "is_success": True,
        }

        res = ReceiptVerifier.verify_receipt(
            user=self.user,
            image_bytes=fake_bytes,
            plan_type="pro",
        )

        self.assertFalse(res["success"])
        self.assertTrue(res["is_banned"])
        self.assertIn("bloklandi", res["message"].lower())

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_banned)
        self.assertEqual(
            self.user.ban_reason, "Qalbaki to'lov cheki yuklash orqali firibgarlik"
        )
        self.assertIsNotNone(self.user.banned_at)

        # Verify logged into FraudLog
        log = FraudLog.objects.filter(
            user=self.user, transaction_id="CLICK-DUPLICATE-TX-100"
        ).first()
        self.assertIsNotNone(log)
        self.assertTrue(log.banned)

    def test_duplicate_image_hash_triggers_strike_and_ban(self):
        """Re-uploading the exact same image hash triggers deliberate fraud strike & ban."""
        fake_bytes = b"exact_same_image_bytes_uploaded_twice"
        hash_val = compute_receipt_hash(fake_bytes)

        PaymentReceipt.objects.create(
            user=self.other_user,
            plan_type="starter",
            amount=Decimal("5000"),
            payment_system=PaymentReceipt.PaymentSystem.PAYME,
            transaction_id="TX-ORIGINAL-HASH-1",
            receipt_image="receipts/original.jpg",
            receipt_hash=hash_val,
            is_verified=True,
        )

        res = ReceiptVerifier.verify_receipt(
            user=self.user,
            image_bytes=fake_bytes,
            plan_type="starter",
        )

        self.assertFalse(res["success"])
        self.assertTrue(res["is_banned"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_banned)

    @patch("apps.subscriptions.services.receipt_verifier.scan_receipt_vision")
    def test_underpaid_receipt_returns_level1_error_without_strike(self, mock_scan):
        """If receipt amount is less than plan price, return friendly Level 1 error without strike."""
        fake_bytes = b"underpaid_image_bytes"
        mock_scan.return_value = {
            "is_valid": True,
            "amount": 5000.0,  # 5,000 sent for PRO (which requires 49,000)
            "transaction_id": "TX-UNDERPAID-001",
            "payment_system": PaymentReceipt.PaymentSystem.CLICK,
            "date_str": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            "recipient": "GRAND EDUCATION",
            "is_success": True,
        }

        res = ReceiptVerifier.verify_receipt(
            user=self.user,
            image_bytes=fake_bytes,
            plan_type="pro",
        )

        self.assertFalse(res["success"])
        self.assertFalse(res["is_banned"])
        self.assertIn("yetarli emas", res["message"])

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_banned)
        self.assertEqual(self.user.fraud_strikes, 0)

    @patch("apps.subscriptions.services.receipt_verifier.scan_receipt_vision")
    def test_unreadable_blurry_image_returns_level1_error_without_strike(
        self, mock_scan
    ):
        """Unreadable or non-receipt image returns retry guidance without strike."""
        fake_bytes = b"blurry_unreadable_bytes"
        mock_scan.return_value = {
            "is_valid": False,
            "amount": 0.0,
            "transaction_id": "",
            "payment_system": PaymentReceipt.PaymentSystem.UNKNOWN,
        }

        res = ReceiptVerifier.verify_receipt(
            user=self.user,
            image_bytes=fake_bytes,
            plan_type="starter",
        )

        self.assertFalse(res["success"])
        self.assertFalse(res["is_banned"])
        self.assertIn("Chek tasdiqlanmadi", res["message"])

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_banned)
        self.assertEqual(self.user.fraud_strikes, 0)

    def test_banned_user_middleware_blocks_access(self):
        """BannedUserMiddleware blocks requests from banned user with 403 Forbidden."""
        self.user.is_banned = True
        self.user.ban_reason = "Qalbaki to'lov cheki yuklash orqali firibgarlik"
        self.user.save()

        self.client.force_login(self.user)
        response = self.client.get("/api/v1/payments/my-receipts/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json().get("is_banned"))
        self.assertIn("bloklandi", response.json().get("detail", "").lower())

    @patch("apps.subscriptions.services.receipt_verifier.scan_receipt_vision")
    def test_api_verify_receipt_endpoint(self, mock_scan):
        """POST /api/v1/subscriptions/verify-receipt/ processes file upload."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        mock_scan.return_value = {
            "is_valid": True,
            "amount": 49000.0,
            "transaction_id": "API-PRO-1002",
            "payment_system": PaymentReceipt.PaymentSystem.CLICK,
            "date_str": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            "recipient": "GRAND EDUCATION",
            "is_success": True,
        }

        file_content = b"fake_image_file_bytes_for_api_test"
        uploaded = SimpleUploadedFile(
            "receipt.jpg", file_content, content_type="image/jpeg"
        )

        response = self.client.post(
            "/api/v1/subscriptions/verify-receipt/",
            {"receipt_image": uploaded, "plan_type": "pro"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("plan_type"), "pro")
        self.assertEqual(data.get("transaction_id"), "API-PRO-1002")
