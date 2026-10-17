"""Tests for overhauled Telegram Bot & Notifications features."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.courses.models import Course, StudentGroup
from apps.essays.models import EssaySubmission, EssayTopic
from apps.notifications.bot.handlers import (
    _arena_keyboard,
    _main_menu_keyboard,
    _persistent_menu_keyboard,
    arena_answer_callback,
    arena_bot_start_callback,
    arena_callback_handler,
    arena_finish_callback,
    arena_invite_callback,
    arena_next_callback,
    auth_conversation_handler,
    callback_handler,
    certificate_download_callback,
    certificates_handler,
    essay_check_callback,
    essay_improve_callback,
    essay_review_callback,
    essay_topic_select_callback,
    essays_handler,
    myattendance_handler,
    myplan_handler,
    mytuition_handler,
    payment_screenshot_handler,
    tests_handler as bot_tests_handler,
)
from apps.notifications.bot.quiz import quiz_callback_handler
from apps.notifications.services.telegram_service import TelegramService
from apps.payments.models import PaymentReceipt
from apps.results.models import Certificate, Result
from apps.tests.models import Choice, Question, Test


class TelegramBotFeaturesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test-student@example.test",
            password="StrongPassword123!",
            first_name="Ali",
            last_name="Valiyev",
            role="student",
            telegram_chat_id=99887766,
            telegram_identity_verified_at=timezone.now(),
        )
        self.message = SimpleNamespace(
            text="Matn",
            reply_text=AsyncMock(),
            chat=SimpleNamespace(id=self.user.telegram_chat_id, type="private"),
            message_id=101,
        )
        self.query = SimpleNamespace(
            data="",
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            message=self.message,
        )
        self.update = SimpleNamespace(
            effective_user=SimpleNamespace(
                id=self.user.telegram_chat_id,
                first_name="Ali",
                last_name="Valiyev",
                username="alivaliyev",
            ),
            effective_chat=SimpleNamespace(id=self.user.telegram_chat_id, type="private"),
            message=self.message,
            callback_query=None,
        )
        self.context = SimpleNamespace(
            args=[],
            user_data={},
            bot=SimpleNamespace(
                send_message=AsyncMock(),
                send_document=AsyncMock(),
            ),
        )

    # 1. Terminology & Main Menu
    def test_main_menu_keyboard_uses_esse_terminology(self):
        keyboard = _main_menu_keyboard()
        button_texts = [btn.text for row in keyboard.inline_keyboard for btn in row]
        combined = " ".join(button_texts)
        self.assertIn("Esse yozish", combined)
        self.assertNotIn("insho", combined.lower())

    # 2. Topic selection & interactive flow
    def test_essays_handler_lists_topics_with_inline_buttons(self):
        topic = EssayTopic.objects.create(
            title="Ona tili va milliy o'zlik",
            description="Mavzu tavsifi",
            word_limit_min=150,
            word_limit_max=350,
            time_limit_minutes=45,
            is_active=True,
        )
        async_to_sync(essays_handler)(self.update, self.context)

        reply_call = self.message.reply_text.await_args
        self.assertIsNotNone(reply_call)
        text = reply_call.args[0]
        self.assertIn("Ona tili va milliy o'zlik", text)
        markup = reply_call.kwargs.get("reply_markup")
        self.assertIsNotNone(markup)
        callback_datas = [btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data]
        self.assertIn(f"cb_topic_select:{topic.id}", callback_datas)
        self.assertIn("cb_topic_select:0", callback_datas)

    def test_essay_topic_select_callback(self):
        topic = EssayTopic.objects.create(
            title="Mustaqillik buyuk ne'mat",
            description="Tavsif",
            word_limit_min=100,
            word_limit_max=300,
            time_limit_minutes=30,
            is_active=True,
        )
        self.update.callback_query = self.query
        self.query.data = f"cb_topic_select:{topic.id}"

        async_to_sync(essay_topic_select_callback)(self.update, self.context, topic.id)

        self.assertEqual(self.context.user_data.get("bot_essay_state"), "awaiting_submission")
        self.assertEqual(self.context.user_data.get("bot_essay_topic_id"), topic.id)
        self.assertTrue(self.message.reply_text.called or self.query.edit_message_text.called)

    # 3. Post-grading AI improve and teacher review actions
    def test_telegram_service_send_essay_graded_includes_action_buttons(self):
        submission = EssaySubmission.objects.create(
            student=self.user,
            essay_text="Bu sinov uchun yozilgan ajoyib esse matni.",
            status=EssaySubmission.Status.GRADED,
            total_score=20,
            max_score=24,
            summary="Yaxshi yozilgan esse.",
        )
        with patch.object(TelegramService, "send_message_with_keyboard", return_value={"success": True}) as mock_send:
            TelegramService.send_essay_graded(self.user.telegram_chat_id, submission)
            self.assertTrue(mock_send.called)
            kwargs = mock_send.call_args[1]
            text = kwargs["text"]
            buttons = kwargs["buttons"]
            self.assertIn("Essingiz baholandi", text)
            callbacks = [btn["callback_data"] for row in buttons for btn in row if "callback_data" in btn]
            self.assertIn(f"essay_improve:{submission.id}", callbacks)
            self.assertIn(f"essay_review:{submission.id}", callbacks)

    def test_essay_check_callback(self):
        submission = EssaySubmission.objects.create(
            student=self.user,
            essay_text="Esse matni",
            status=EssaySubmission.Status.GRADED,
            total_score=18,
            max_score=24,
            summary="Ajoyib yozilgan.",
        )
        self.update.callback_query = self.query
        async_to_sync(essay_check_callback)(self.update, self.context, submission.id)

        reply_args = self.message.reply_text.await_args
        self.assertIsNotNone(reply_args)
        text = reply_args.args[0]
        self.assertIn("ESSE NATIJASI", text)
        markup = reply_args.kwargs.get("reply_markup")
        callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data]
        self.assertIn(f"essay_improve:{submission.id}", callbacks)
        self.assertIn(f"essay_review:{submission.id}", callbacks)

    @patch("apps.essays.services.generate_improved_essay")
    def test_essay_improve_callback(self, mock_improve):
        mock_improve.return_value = "Bu AI tomonidan takomillashtirilgan yangi mukammal esse varianti."
        submission = EssaySubmission.objects.create(
            student=self.user,
            essay_text="Oddiy qoralama esse matni.",
            status=EssaySubmission.Status.GRADED,
            total_score=15,
        )
        self.update.callback_query = self.query
        async_to_sync(essay_improve_callback)(self.update, self.context, submission.id)

        reply_args = self.message.reply_text.await_args
        self.assertIsNotNone(reply_args)
        text = reply_args.args[0]
        self.assertIn("AI orqali qayta yozilgan variant", text)
        self.assertIn("takomillashtirilgan", text)

    @patch("apps.essays.services.TeacherReviewService.request_teacher_review")
    def test_essay_review_callback(self, mock_req):
        submission = EssaySubmission.objects.create(
            student=self.user,
            essay_text="Esse matni",
            status=EssaySubmission.Status.GRADED,
        )
        self.update.callback_query = self.query
        async_to_sync(essay_review_callback)(self.update, self.context, submission.id)

        self.assertTrue(mock_req.called)
        reply_args = self.message.reply_text.await_args
        self.assertIn("Ustoz ko'rigiga yuborildi", reply_args.args[0])

    # 4. Certificates and PDF direct delivery
    def test_certificates_handler_and_download_callback(self):
        from apps.tests.models import TestAttempt
        course = Course.objects.create(title="Ona tili asoslari", slug="ona-tili", teacher=self.user)
        test = Test.objects.create(title="Yakuniy attestatsiya", course=course)
        attempt = TestAttempt.objects.create(
            test=test, student=self.user, status=TestAttempt.Status.COMPLETED,
        )
        result = Result.objects.create(
            student=self.user,
            test=test,
            attempt=attempt,
            course=course,
            total_questions=10,
            correct_answers=9,
            wrong_answers=1,
            score=90,
            max_score=100,
            percentage=90.0,
            is_passed=True,
        )
        cert = Certificate.objects.create(
            student=self.user,
            result=result,
            test=test,
            course=course,
            certificate_number="CERT-99901",
        )
        # Test listing
        async_to_sync(certificates_handler)(self.update, self.context)
        reply_args = self.message.reply_text.await_args
        self.assertIsNotNone(reply_args)
        self.assertIn("CERT-99901", reply_args.args[0])

        # Test download callback when file exists
        from django.core.files.base import ContentFile
        cert.file.save("test_cert.pdf", ContentFile(b"%PDF-1.4 test"))

        self.update.callback_query = self.query
        async_to_sync(certificate_download_callback)(self.update, self.context, cert.id)
        self.assertTrue(self.context.bot.send_document.called)
        doc_args = self.context.bot.send_document.call_args[1]
        self.assertEqual(doc_args["chat_id"], self.user.telegram_chat_id)
        self.assertIn("CERT-99901", doc_args["caption"])

    # 5. Arena 1v1 Bot Duel in Telegram Chat
    def test_arena_bot_duel_complete_flow(self):
        # 5.1 Start duel
        self.update.callback_query = self.query
        async_to_sync(arena_bot_start_callback)(self.update, self.context)

        duel_state = self.context.user_data.get("arena_duel")
        self.assertIsNotNone(duel_state)
        room_code = duel_state["room_code"]
        self.assertIsNotNone(room_code)

        # 5.2 Answer question 0
        async_to_sync(arena_answer_callback)(self.update, self.context, room_code, 0, "a")
        duel_state = self.context.user_data.get("arena_duel")
        self.assertGreaterEqual(duel_state.get("player_score", 0), 0)

        # 5.3 Next question
        async_to_sync(arena_next_callback)(self.update, self.context, room_code, 1)

        # 5.4 Finish duel
        async_to_sync(arena_finish_callback)(self.update, self.context, room_code)
        reply_args = self.message.reply_text.await_args
        self.assertIn("ARENA DUEL YAKUNLANDI", reply_args.args[0])

    # 6. Payment, Plan and Attendance cards
    def test_myplan_card_layout(self):
        async_to_sync(myplan_handler)(self.update, self.context)
        reply_args = self.message.reply_text.await_args
        self.assertIsNotNone(reply_args)
        text = reply_args.args[0]
        self.assertIn("TARIF REJASI KARTASI", text)
        self.assertIn("Joriy tarif", text)

    def test_mytuition_card_layout(self):
        async_to_sync(mytuition_handler)(self.update, self.context)
        reply_args = self.message.reply_text.await_args
        self.assertIsNotNone(reply_args)
        text = reply_args.args[0]
        self.assertIn("KURS TO'LOVLARI", text)

    def test_myattendance_card_layout(self):
        group = StudentGroup.objects.create(name="10-A Guruh", teacher=self.user)
        session = AttendanceSession.objects.create(
            group=group, teacher=self.user, lesson_date=timezone.now().date(),
        )
        AttendanceRecord.objects.create(
            session=session,
            student=self.user,
            status=AttendanceRecord.Status.PRESENT,
        )
        async_to_sync(myattendance_handler)(self.update, self.context)
        reply_args = self.message.reply_text.await_args
        self.assertIsNotNone(reply_args)
        text = reply_args.args[0]
        self.assertIn("DAVOMAT KARTASI", text)
        self.assertIn("100.0%", text)

    # 7. Robust callback query error handling
    def test_callback_handler_catches_errors_and_offers_main_menu(self):
        self.update.callback_query = self.query
        self.query.data = "cb_topic_select:invalid_id"

        # Even with completely malformed data, it should not raise an exception
        async_to_sync(callback_handler)(self.update, self.context)
        # Should reply or answer without crashing
        self.assertTrue(self.message.reply_text.called or self.query.edit_message_text.called)

    def test_arena_callback_handler_dispatch(self):
        self.update.callback_query = self.query
        self.query.data = "arena_lb"
        async_to_sync(arena_callback_handler)(self.update, self.context)
        self.assertTrue(self.query.edit_message_text.called)
        args = self.query.edit_message_text.await_args.args[0]
        self.assertIn("ELO REYTING", args)

    def test_arena_keyboard_and_invite_creation(self):
        keyboard = _arena_keyboard()
        button_texts = [btn.text for row in keyboard.inline_keyboard for btn in row]
        combined = " ".join(button_texts)
        self.assertIn("Do'stni duelga chorlash", combined)

        self.update.callback_query = self.query
        self.query.data = "arena_create"
        async_to_sync(arena_callback_handler)(self.update, self.context)
        self.assertTrue(self.query.edit_message_text.called)
        text = self.query.edit_message_text.await_args.args[0]
        self.assertIn("DUEL XONASI YARATILDI", text)
        markup = self.query.edit_message_text.await_args.kwargs.get("reply_markup")
        share_btns = [btn for row in markup.inline_keyboard for btn in row if "t.me/share" in (getattr(btn, "url", None) or "")]
        self.assertTrue(len(share_btns) > 0)

    # 8. TMA REST API endpoints
    def test_tma_rest_api_certificates_myplan_mytuition(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        # Certificates
        res_cert = client.get("/tma/api/certificates/")
        self.assertEqual(res_cert.status_code, 200)
        self.assertIn("certificates", res_cert.json())

        # My Plan
        res_plan = client.get("/tma/api/myplan/")
        self.assertEqual(res_plan.status_code, 200)
        self.assertIn("plan_name", res_plan.json())

        # My Tuition
        res_tui = client.get("/tma/api/mytuition/")
        self.assertEqual(res_tui.status_code, 200)
        self.assertIn("tuition", res_tui.json())

    # 9. Test handler & test format options
    def test_tests_handler_shows_fast_cbt_and_quiz_and_mock(self):
        async_to_sync(bot_tests_handler)(self.update, self.context)
        self.assertTrue(self.message.reply_text.called)
        text = self.message.reply_text.await_args.args[0]
        self.assertIn("Fast CBT", text)
        self.assertIn("Telegram Chat Quiz", text)
        self.assertIn("Mock Test", text)
        markup = self.message.reply_text.await_args.kwargs.get("reply_markup")
        btn_data = [getattr(btn, "callback_data", None) for row in markup.inline_keyboard for btn in row]
        self.assertIn("menu_quiz", btn_data)
        self.assertIn("menu_mock_join", btn_data)

    # 10. Persistent menu keyboard layout
    def test_persistent_menu_keyboard_layout(self):
        markup = _persistent_menu_keyboard()
        buttons = [[btn.text for btn in row] for row in markup.keyboard]
        self.assertEqual(len(buttons), 3)
        self.assertEqual(buttons[0], ["✍️ Esse yozish", "📚 Test ishlash"])
        self.assertEqual(buttons[1], ["📝 Mock Test (#kod)", "⚔️ Arena (1v1)"])
        self.assertEqual(buttons[2], ["👤 Natijalar / Profil", "💳 Tariflar / Obuna"])

    # 11. Quiz mistake AI explainer
    def test_quiz_explain_callback_returns_explanation(self):
        course = Course.objects.create(
            title="Ona tili",
            slug="ona-tili-quiz-test",
            teacher=self.user,
        )
        test = Test.objects.create(
            course=course,
            title="Grammatika",
            time_limit_minutes=10,
            pass_percentage=60,
        )
        q = Question.objects.create(
            test=test,
            text="Qaysi gapda ergashgan qo'shma gap berilgan?",
            question_type=Question.QuestionType.SINGLE_CHOICE,
            explanation="Ergash gap bosh gapga bog'lovchi orqali birikadi.",
        )
        c_wrong = Choice.objects.create(question=q, text="Sodda gap varianti", is_correct=False)
        Choice.objects.create(question=q, text="To'g'ri ergashgan gap", is_correct=True)

        self.user.profile.plan = "premium"
        self.user.profile.save()

        self.update.callback_query = self.query
        self.query.data = f"quiz_explain_{q.id}_{c_wrong.id}"
        async_to_sync(quiz_callback_handler)(self.update, self.context)
        self.assertTrue(self.message.reply_text.called)
        reply_text = self.message.reply_text.await_args.args[0]
        self.assertIn("AI REPETITOR TAHLILI", reply_text)
        self.assertIn("Nega bu javob xato", reply_text)

    # 12. Mock test code join via chat
    def test_auth_conversation_handler_mock_code_join(self):
        course = Course.objects.create(
            title="Mock Kurs",
            slug="mock-kurs-test",
            teacher=self.user,
        )
        test = Test.objects.create(
            course=course,
            title="Milliy Sertifikat Mock #MOCK-999",
            mock_code="#MOCK-999",
            time_limit_minutes=60,
            pass_percentage=46,
            is_active=True,
        )
        self.message.text = "#MOCK-999"
        async_to_sync(auth_conversation_handler)(self.update, self.context)
        self.assertTrue(self.message.reply_text.called)
        reply_text = self.message.reply_text.await_args.args[0]
        self.assertIn("MOCK TEST TOPILDI", reply_text)
        markup = self.message.reply_text.await_args.kwargs.get("reply_markup")
        btn_data = [btn.callback_data for row in markup.inline_keyboard for btn in row if getattr(btn, "callback_data", None)]
        self.assertIn(f"quiz_start_{test.id}", btn_data)

    # 13. Fallback on unrecognized text
    def test_auth_conversation_handler_unrecognized_text_fallback(self):
        self.message.text = "tushunarsiz tasodifiy matn 123"
        async_to_sync(auth_conversation_handler)(self.update, self.context)
        self.assertTrue(self.message.reply_text.called)
        reply_text = self.message.reply_text.await_args.args[0]
        self.assertIn("Kerakli bo'limni tanlash uchun quyidagi menyu tugmalaridan foydalaning", reply_text)
        markup = self.message.reply_text.await_args.kwargs.get("reply_markup")
        self.assertIsNotNone(markup)

    # 14. Payment receipt screenshot upload
    def test_payment_screenshot_handler_creates_receipt(self):
        self.context.user_data["selected_plan_slug"] = "starter"
        self.context.user_data["payment_state"] = "awaiting_screenshot"
        valid_mock_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 64
        self.message.photo = [
            SimpleNamespace(
                get_file=AsyncMock(
                    return_value=SimpleNamespace(
                        download_as_bytearray=AsyncMock(return_value=valid_mock_jpeg)
                    )
                )
            )
        ]
        self.message.caption = "Starter to'lov cheki"
        async_to_sync(payment_screenshot_handler)(self.update, self.context)

        receipt = PaymentReceipt.objects.filter(user=self.user, plan="starter").order_by("-id").first()
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.source, PaymentReceipt.Source.BOT)
        self.assertEqual(receipt.status, PaymentReceipt.Status.PENDING)
        self.assertTrue(self.message.reply_text.called)
        reply_text = self.message.reply_text.await_args.args[0]
        self.assertIn("Chekingiz qabul qilindi", reply_text)

    # 15. Telegram Login Widget (1-Click Auth)
    @override_settings(TELEGRAM_BOT_TOKEN="test_bot_token_12345")
    def test_telegram_widget_auth_success(self):
        import hashlib
        import hmac
        import time
        client = APIClient()
        tg_id = 123456789
        auth_date = int(time.time())
        data_to_sign = {
            "auth_date": auth_date,
            "first_name": "WidgetUser",
            "id": tg_id,
            "username": "widget_user",
        }
        check_items = [f"{k}={data_to_sign[k]}" for k in sorted(data_to_sign.keys())]
        check_string = "\n".join(check_items)
        secret_key = hashlib.sha256("test_bot_token_12345".encode()).digest()
        computed_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        data_to_sign["hash"] = computed_hash

        resp = client.post("/api/auth/telegram/widget/", data=data_to_sign, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "ok")
        self.assertIn("tokens", resp.data)
        self.assertIn("access", resp.data["tokens"])
        self.assertEqual(resp.data["user"]["full_name"], "WidgetUser")


