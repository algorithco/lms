from decimal import Decimal
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.courses.models import Course, StudentGroup
from apps.notifications.bot.group_assistant import (
    group_attendance_callback,
    group_davomat_command,
    group_davomat_yakun_command,
    group_results_leaderboard_command,
    group_yangi_test_command,
    link_group_command,
    ustoz_menu_command,
)
from apps.payments.models import PaymentReceipt
from apps.results.models import Result
from apps.tests.models import Test

User = get_user_model()


class BillingReceiptCSRFTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="student_csrf_test@grandec.uz",
            password="PassWord123!",
            first_name="Sardor",
            last_name="Karimov",
            role="student",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_receipt_upload_csrf_exempt_and_instant_trial(self):
        """Verify that uploading a receipt succeeds without CSRF token and activates 24h trial."""
        buf = BytesIO()
        Image.new("RGB", (100, 100), color="blue").save(buf, format="PNG")
        uploaded = SimpleUploadedFile("receipt.png", buf.getvalue(), content_type="image/png")

        with patch("apps.payments.services.requests.post") as mock_tg_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_tg_post.return_value = mock_resp

            response = self.client.post(
                "/api/v1/billing/upload-receipt/",
                {
                    "tariff": "PRO",
                    "amount": "15000",
                    "receipt_image": uploaded,
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data.get("trial_granted"))
        self.assertEqual(data.get("trial_hours"), 24)
        self.assertIn("24 SOATLIK PRO TRIAL", data.get("message", ""))

        # Verify receipt saved in DB
        receipt = PaymentReceipt.objects.filter(user=self.user).first()
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.plan, "pro")
        self.assertEqual(receipt.amount, Decimal("15000"))

        # Verify Telegram notification was sent to superadmin 5582178765
        self.assertTrue(mock_tg_post.called)
        called_args = mock_tg_post.call_args_list
        admin_ids = [c[1].get("data", {}).get("chat_id") or c[1].get("json", {}).get("chat_id") for c in called_args]
        self.assertIn(5582178765, admin_ids)


class TelegramGroupBotAssistantTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="teacher_bot_test@grandec.uz",
            password="PassWord123!",
            first_name="Hamid",
            last_name="Olimjon",
            role="teacher",
            telegram_chat_id=987654321,
        )
        self.student = User.objects.create_user(
            email="student_group_test@grandec.uz",
            password="PassWord123!",
            first_name="Diyorbek",
            last_name="Xoldorov",
            role="student",
            telegram_chat_id=555666777,
        )

    def test_telegram_bot_link_group(self):
        """Verify /link_group command binds StudentGroup to telegram_chat_id."""
        group = StudentGroup.objects.create(
            teacher=self.teacher,
            name="11-A Ona tili guruhi",
            invite_code="GR-11A",
        )

        update = MagicMock()
        update.effective_chat.id = -1001234567890
        update.effective_chat.type = "supergroup"
        update.effective_user.id = 987654321
        update.effective_user.username = "hamid_teacher"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = ["GR-11A"]

        async_to_sync(link_group_command)(update, context)

        # Check reply
        self.assertTrue(update.message.reply_text.called)
        reply_text = update.message.reply_text.call_args[0][0]
        self.assertIn("Guruh muvaffaqiyatli bog'landi!", reply_text)
        self.assertIn("11-A Ona tili guruhi", reply_text)

        # Verify group updated
        group.refresh_from_db()
        self.assertEqual(group.telegram_chat_id, -1001234567890)

    def test_telegram_bot_davomat_and_yakun(self):
        """Verify /davomat and /davomat_yakun attendance flow and LMS DB synchronization."""
        group = StudentGroup.objects.create(
            teacher=self.teacher,
            name="10-B Sinf",
            invite_code="GR-10B",
            telegram_chat_id=-1009876543210,
        )
        group.students.add(self.student)

        # 1. Teacher starts /davomat
        update_dav = MagicMock()
        update_dav.effective_chat.id = -1009876543210
        update_dav.effective_chat.type = "supergroup"
        msg_mock = MagicMock()
        msg_mock.message_id = 42
        update_dav.message.reply_text = AsyncMock(return_value=msg_mock)

        context = MagicMock()
        context.bot_data = {}

        async_to_sync(group_davomat_command)(update_dav, context)
        self.assertTrue(update_dav.message.reply_text.called)
        dav_text = update_dav.message.reply_text.call_args[0][0]
        self.assertIn("KUNLIK DAVOMAT", dav_text)

        # 2. Student clicks 'Keldim'
        update_click = MagicMock()
        update_click.effective_chat.id = -1009876543210
        update_click.effective_user.id = 555666777
        update_click.effective_user.full_name = "Diyorbek Xoldorov"
        update_click.effective_user.username = "diyorbek_x"
        update_click.callback_query.data = f"grp_att_here_{group.id}"
        update_click.callback_query.answer = AsyncMock()
        update_click.callback_query.edit_message_text = AsyncMock()

        async_to_sync(group_attendance_callback)(update_click, context)
        self.assertTrue(update_click.callback_query.answer.called)

        # 3. Teacher ends attendance with /davomat_yakun
        update_yakun = MagicMock()
        update_yakun.effective_chat.id = -1009876543210
        update_yakun.effective_chat.type = "supergroup"
        update_yakun.message.reply_text = AsyncMock()

        async_to_sync(group_davomat_yakun_command)(update_yakun, context)
        self.assertTrue(update_yakun.message.reply_text.called)
        yakun_text = update_yakun.message.reply_text.call_args[0][0]
        self.assertIn("DAVOMAT YAKUNI", yakun_text)
        self.assertIn("Diyorbek Xoldorov", yakun_text)

        # Verify session in LMS DB
        session = AttendanceSession.objects.filter(group=group).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, AttendanceSession.Status.FINALIZED)

    def test_telegram_bot_yangi_test_and_leaderboard(self):
        """Verify /yangi_test and /leaderboard commands."""
        course = Course.objects.create(
            teacher=self.teacher,
            title="Ona tili kursi",
            slug="ona-tili-kursi-test-group",
        )
        test_obj = Test.objects.create(
            course=course,
            title="BMB Milliy Sertifikat Variant 1",
            time_limit_minutes=60,
        )

        group = StudentGroup.objects.create(
            teacher=self.teacher,
            name="11-A Sinf",
            invite_code="GR-11A",
            telegram_chat_id=-1001112223334,
        )
        group.students.add(self.student)

        # 1. Test announcement
        update_test = MagicMock()
        update_test.effective_chat.id = -1001112223334
        update_test.effective_chat.type = "supergroup"
        update_test.message.reply_text = AsyncMock()

        context = MagicMock()
        async_to_sync(group_yangi_test_command)(update_test, context)

        self.assertTrue(update_test.message.reply_text.called)
        msg_text = update_test.message.reply_text.call_args[0][0]
        self.assertIn("BMB Milliy Sertifikat Variant 1", msg_text)
        self.assertIn("Kirish PIN-kodi:", msg_text)
        reply_markup = update_test.message.reply_text.call_args[1]["reply_markup"]
        self.assertIsNotNone(reply_markup.inline_keyboard[0][0].web_app)

        # 2. Leaderboard
        from apps.tests.models import TestAttempt

        attempt = TestAttempt.objects.create(
            student=self.student,
            test=test_obj,
            status=TestAttempt.Status.COMPLETED,
        )
        Result.objects.create(
            attempt=attempt,
            student=self.student,
            test=test_obj,
            course=course,
            total_questions=30,
            correct_answers=28,
            wrong_answers=2,
            score=Decimal("94.0"),
            max_score=Decimal("100.0"),
            percentage=Decimal("94.0"),
            is_passed=True,
        )

        update_lb = MagicMock()
        update_lb.effective_chat.id = -1001112223334
        update_lb.effective_chat.type = "supergroup"
        update_lb.message.reply_text = AsyncMock()

        async_to_sync(group_results_leaderboard_command)(update_lb, context)
        self.assertTrue(update_lb.message.reply_text.called)
        lb_text = update_lb.message.reply_text.call_args[0][0]
        self.assertIn("Guruhi Test Natijalari:", lb_text)
        self.assertIn("94", lb_text)
        self.assertIn("Guruh o'rtacha ko'rsatkichi:", lb_text)
        self.assertIn("Murakkab qo'shma gaplar tahlili", lb_text)

    def test_ustoz_menu_command(self):
        """Verify /ustoz menu command shows teacher groups."""
        StudentGroup.objects.create(
            teacher=self.teacher,
            name="Ona tili Olimpiada",
            invite_code="GR-OLIMP",
        )

        update = MagicMock()
        update.effective_chat.id = 987654321
        update.effective_chat.type = "private"
        update.effective_user.id = 987654321
        update.effective_user.username = "hamid_teacher"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        async_to_sync(ustoz_menu_command)(update, context)

        self.assertTrue(update.message.reply_text.called)
        menu_text = update.message.reply_text.call_args[0][0]
        self.assertIn("Ustoz Menyusi: Hamid Olimjon", menu_text)
        self.assertIn("Ona tili Olimpiada", menu_text)
