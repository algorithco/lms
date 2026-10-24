"""
Tests for Bot Unified Account, Quota Enforcement & Teacher CRM (Modules 1, 2, 3, 4).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache

from apps.accounts.models import User, Profile
from apps.courses.models import StudentGroup, GroupEnrollment
from apps.attendance.models import AttendanceSession, AttendanceRecord
from apps.accounts.services.telegram_link import (
    create_link_challenge,
    confirm_link_challenge,
)
from apps.subscriptions.services import QuotaService
from apps.groups.services import (
    get_teacher_groups,
    get_group_finance_summary,
    record_tuition_payment,
    send_debtor_payment_reminders,
    save_interactive_attendance,
)
from apps.bot.crm import (
    build_davomat_keyboard,
    build_tolovlar_text,
    build_tolovlar_keyboard,
    build_receipt_approval_prompt,
)
from apps.bot.quota import check_bot_essay_quota, get_essay_denied_keyboard


class BotUnifiedAccountTests(TestCase):
    """Module 1: Unified Account & Deep-Link Linking Tests."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="student_link@grandec.uz",
            first_name="Aziz",
            last_name="Karimov",
            role=User.Role.STUDENT,
        )

    def test_create_and_confirm_link_challenge_with_username(self):
        token = create_link_challenge(self.user)
        self.assertTrue(bool(token))

        # Confirm via Telegram numeric id and username
        tg_id = 987654321
        tg_username = "aziz_karimov"
        state = confirm_link_challenge(
            token, telegram_id=tg_id, telegram_username=tg_username
        )

        self.assertEqual(state, "confirmed")
        self.user.refresh_from_db()
        self.assertEqual(self.user.telegram_chat_id, tg_id)
        self.assertEqual(self.user.telegram_id, tg_id)
        self.assertEqual(self.user.telegram_username, tg_username)
        self.assertIsNotNone(self.user.telegram_identity_verified_at)

    def test_link_challenge_conflict(self):
        User.objects.create_user(
            email="existing_tg@grandec.uz",
            first_name="Boshqa",
            last_name="Foydalanuvchi",
            telegram_chat_id=1122334455,
        )
        token = create_link_challenge(self.user)
        state = confirm_link_challenge(token, telegram_id=1122334455)
        self.assertEqual(state, "conflict")


class BotQuotaEnforcementTests(TestCase):
    """Module 2: Quota Enforcement (Free 1-essay limit, Starter/PRO checks)."""

    def setUp(self):
        cache.clear()
        self.free_user = User.objects.create_user(
            email="free_student@grandec.uz",
            first_name="Free",
            last_name="Student",
            role=User.Role.STUDENT,
        )
        Profile.objects.get_or_create(user=self.free_user, defaults={"plan": "free"})

        self.pro_user = User.objects.create_user(
            email="pro_student@grandec.uz",
            first_name="Pro",
            last_name="Student",
            role=User.Role.STUDENT,
        )
        self.pro_user.profile.plan = "pro"
        self.pro_user.profile.save(update_fields=["plan"])

        self.starter_user = User.objects.create_user(
            email="starter_student@grandec.uz",
            first_name="Starter",
            last_name="Student",
            role=User.Role.STUDENT,
        )
        self.starter_user.profile.plan = "starter"
        self.starter_user.profile.save(update_fields=["plan"])

    def test_free_user_first_essay_allowed(self):
        allowed, msg, details = QuotaService.check_essay_quota(self.free_user)
        self.assertTrue(allowed)
        self.assertEqual(details["tier"], "free")
        self.assertEqual(details["remaining"], 1)

    def test_free_user_second_essay_blocked_with_exact_message(self):
        # 1-marta foydalandi
        QuotaService.consume_essay_quota(self.free_user)

        # 2-marta tekshirganda bloklanishi kerak
        allowed, msg, details = QuotaService.check_essay_quota(self.free_user)
        self.assertFalse(allowed)
        self.assertIn("Kvotangiz tugadi!", msg)
        self.assertIn("1 ta bepul esse", msg)
        self.assertIn("Starter", msg)
        self.assertEqual(details["remaining"], 0)

        # Check bot wrapper
        bot_allowed, bot_msg, bot_kb = check_bot_essay_quota(self.free_user)
        self.assertFalse(bot_allowed)
        self.assertIsNotNone(bot_kb)

    def test_pro_user_unlimited_access(self):
        for _ in range(5):
            QuotaService.consume_essay_quota(self.pro_user)
        allowed, msg, details = QuotaService.check_essay_quota(self.pro_user)
        self.assertTrue(allowed)
        self.assertEqual(details["tier"], "pro")

    def test_denied_keyboard_structure(self):
        kb = get_essay_denied_keyboard("https://grandec.uz")
        self.assertEqual(len(kb.inline_keyboard), 2)
        btn_starter = kb.inline_keyboard[0][0]
        btn_pro = kb.inline_keyboard[0][1]
        btn_site = kb.inline_keyboard[1][0]
        self.assertIn("Starter", btn_starter.text)
        self.assertIn("PRO", btn_pro.text)
        self.assertEqual(btn_site.url, "https://grandec.uz/subscribe")


class TeacherBotCrmTests(TestCase):
    """Module 3: Teacher CRM (Attendance, Tuition & Receipt Verification)."""

    def setUp(self):
        cache.clear()
        self.teacher = User.objects.create_user(
            email="teacher_crm@grandec.uz",
            first_name="Rustam",
            last_name="Ustoz",
            role=User.Role.TEACHER,
            telegram_chat_id=554433221,
        )
        self.st1 = User.objects.create_user(
            email="st1_crm@grandec.uz",
            first_name="Alisher",
            last_name="Vohidov",
            role=User.Role.STUDENT,
            telegram_chat_id=111111111,
        )
        self.st2 = User.objects.create_user(
            email="st2_crm@grandec.uz",
            first_name="Sardor",
            last_name="Komilov",
            role=User.Role.STUDENT,
            telegram_chat_id=222222222,
        )

        self.group = StudentGroup.objects.create(
            name="IELTS Intensive 2026",
            teacher=self.teacher,
            monthly_fee=500000.00,
        )
        self.group.students.add(self.st1, self.st2)

    def test_get_teacher_groups(self):
        groups = get_teacher_groups(self.teacher)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].name, "IELTS Intensive 2026")

    def test_group_finance_summary_and_reminders(self):
        # Setup enrollments
        today = timezone.localdate()
        GroupEnrollment.objects.create(
            group=self.group,
            student=self.st1,
            monthly_fee=Decimal("500000.00"),
            payment_status=GroupEnrollment.PaymentStatus.PAID,
            last_payment_date=today,
            next_payment_due=today + timezone.timedelta(days=25),
        )
        GroupEnrollment.objects.create(
            group=self.group,
            student=self.st2,
            monthly_fee=Decimal("500000.00"),
            payment_status=GroupEnrollment.PaymentStatus.OVERDUE,
            next_payment_due=today - timezone.timedelta(days=2),
            parent_telegram_id="999888777",
        )

        summary = get_group_finance_summary(self.group)
        self.assertEqual(summary["total_students"], 2)
        self.assertEqual(summary["paid_count"], 1)
        self.assertEqual(summary["debtor_count"], 1)
        self.assertEqual(summary["collected_amount"], 500000.00)
        self.assertEqual(summary["pending_amount"], 500000.00)

        # Test reminder sending (mocking telegram)
        with patch(
            "apps.groups.services.send_telegram_safe", return_value=True
        ) as mock_send:
            res = send_debtor_payment_reminders(self.teacher, self.group.id)
            self.assertTrue(res["success"])
            self.assertGreaterEqual(res["total_notified"], 1)
            self.assertTrue(mock_send.called)

    def test_save_interactive_attendance_and_parent_alert(self):
        # st1 present, st2 absent
        statuses = {self.st1.id: "present", self.st2.id: "absent"}

        # Add parent telegram id to st2 enrollment
        GroupEnrollment.objects.create(
            group=self.group,
            student=self.st2,
            parent_telegram_id="777666555",
        )

        with patch(
            "apps.groups.services.send_telegram_safe", return_value=True
        ) as mock_alert:
            session, stats = save_interactive_attendance(
                self.group, self.teacher, statuses
            )
            self.assertEqual(session.status, AttendanceSession.Status.FINALIZED)
            self.assertEqual(stats["present"], 1)
            self.assertEqual(stats["absent"], 1)

            # Check records
            rec1 = AttendanceRecord.objects.get(session=session, student=self.st1)
            rec2 = AttendanceRecord.objects.get(session=session, student=self.st2)
            self.assertEqual(rec1.status, AttendanceRecord.Status.PRESENT)
            self.assertEqual(rec2.status, AttendanceRecord.Status.ABSENT)

            # Parent must receive alert
            self.assertTrue(mock_alert.called)

    def test_record_tuition_payment_and_receipt_approval(self):
        today = timezone.localdate()
        enrollment = GroupEnrollment.objects.create(
            group=self.group,
            student=self.st2,
            monthly_fee=Decimal("500000.00"),
            payment_status=GroupEnrollment.PaymentStatus.OVERDUE,
            next_payment_due=today - timezone.timedelta(days=2),
        )

        # Record payment
        updated = record_tuition_payment(enrollment, amount=500000)
        self.assertEqual(updated.payment_status, GroupEnrollment.PaymentStatus.PAID)
        self.assertEqual(updated.last_payment_date, today)
        self.assertEqual(updated.next_payment_due, today + timezone.timedelta(days=30))

    def test_crm_keyboard_and_prompt_builders(self):
        # Davomat keyboard
        kb = build_davomat_keyboard(
            self.group.id,
            [self.st1, self.st2],
            {self.st1.id: "present", self.st2.id: "absent"},
        )
        self.assertIsNotNone(kb)
        btn_texts = [b.text for row in kb.inline_keyboard for b in row]
        self.assertTrue(any("🟢" in t for t in btn_texts))
        self.assertTrue(any("🔴" in t for t in btn_texts))
        self.assertTrue(any("Saqlash" in t for t in btn_texts))

        # Tolovlar text
        text = build_tolovlar_text(
            {
                "group_name": "Test Group",
                "total_students": 10,
                "paid_count": 8,
                "debtor_count": 2,
                "collected_amount": 4000000,
                "pending_amount": 1000000,
                "debtors": [],
            }
        )
        self.assertIn("KURS TO'LOVLARI HISOBOTI", text)
        self.assertIn("10 ta", text)

        # Receipt prompt
        p_text, p_kb = build_receipt_approval_prompt(
            "Alisher V.", "IELTS Group", 500000, 1
        )
        self.assertIn("Alisher V.", p_text)
        self.assertIn("500 000 so'm", p_text)
        self.assertEqual(p_kb.inline_keyboard[0][0].text, "✅ Tasdiqlash")
        self.assertEqual(p_kb.inline_keyboard[0][1].text, "❌ Rad etish")


class BotHandlersEndToEndTests(TestCase):
    """End-to-end tests for /davomat, /tolovlar, and CRM callbacks."""

    def setUp(self):
        cache.clear()
        self.teacher = User.objects.create_user(
            email="teacher_e2e@grandec.uz",
            first_name="Zafar",
            last_name="Muallim",
            role=User.Role.TEACHER,
            telegram_chat_id=88990011,
        )
        self.student = User.objects.create_user(
            email="student_e2e@grandec.uz",
            first_name="Otabek",
            last_name="Toshov",
            role=User.Role.STUDENT,
            telegram_chat_id=33445566,
        )
        self.group = StudentGroup.objects.create(
            name="CEFR B2 Group",
            teacher=self.teacher,
            monthly_fee=400000.00,
        )
        self.group.students.add(self.student)

    async def test_davomat_and_tolovlar_handlers(self):
        from apps.bot.crm import davomat_handler, tolovlar_handler, handle_crm_callback

        from unittest.mock import AsyncMock

        # Mock update for /davomat
        update = MagicMock()
        update.effective_user.id = self.teacher.telegram_chat_id
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.user_data = {}

        await davomat_handler(update, context)
        self.assertTrue(update.message.reply_text.called)
        args, kwargs = update.message.reply_text.call_args
        self.assertIn("TEZKOR INTERAKTIV DAVOMAT", args[0])

        # Test /tolovlar
        update.message.reply_text.reset_mock()
        await tolovlar_handler(update, context)
        self.assertTrue(update.message.reply_text.called)
        args, kwargs = update.message.reply_text.call_args
        self.assertIn("KURS TO'LOVLARI HISOBOTI", args[0])

        # Test dav_save callback
        query_update = MagicMock()
        query_update.effective_user.id = self.teacher.telegram_chat_id
        query_update.callback_query.edit_message_text = AsyncMock()
        context.user_data[f"dav_statuses_{self.group.id}"] = {
            self.student.id: "present"
        }

        await handle_crm_callback(query_update, context, f"dav_save_{self.group.id}")
        self.assertTrue(query_update.callback_query.edit_message_text.called)
        c_args, _ = query_update.callback_query.edit_message_text.call_args
        self.assertIn("davomati muvaffaqiyatli saqlandi", c_args[0])
