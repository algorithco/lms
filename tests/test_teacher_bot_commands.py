"""Telegram teacher commands — registration, authorization and the register flow.

The bot is the primary teacher interface for attendance, so these tests drive the
real handlers (``asgiref.sync.async_to_sync`` over ``SimpleNamespace`` updates,
exactly like ``tests.test_essay_bot_submit``) against the real ORM and the
canonical ``apps.attendance`` / ``apps.essays.group_reports`` services.

Three rules are treated as hard requirements:

* a teacher only ever sees their own groups' data, whoever the sender claims to be;
* finalizing a register never invents absences for unmarked students;
* a shared/group-facing text is aggregate only.
"""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from asgiref.sync import async_to_sync
from django.test import TestCase
from django.utils import timezone
from telegram.ext import CommandHandler

from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.attendance.services import create_session, finalize, mark
from apps.courses.models import StudentGroup
from apps.weekly_reports import services as weekly_report_services
from apps.weekly_reports.models import WeeklyGroupReport
from apps.essays.models import EssayAssignment, EssaySubmission, EssayTopic
from apps.notifications.bot import handlers

TEACHER_TG = 51000001
OTHER_TEACHER_TG = 51000002
STUDENT_TG = 51000003
UNLINKED_TG = 51000009

#: Command -> handler function name in ``handlers``. A rename that drops a
#: command from the bot must fail here rather than silently in production.
TEACHER_COMMANDS = {
    "groups": "groups_handler",
    "attendance": "attendance_handler",
    "attendance_report": "attendance_report_handler",
    "students": "students_handler",
    "essay_results": "essay_results_handler",
    "group_report": "group_report_handler",
    "mytuition": "mytuition_handler",
    "course_payment": "course_payment_handler",
    "payment_history": "payment_history_handler",
    "payment_proof": "payment_proof_handler",
    "weekly_report": "weekly_report_handler",
    "group_payments": "group_payments_handler",
}


def _texts(*mocks):
    """Every first positional argument passed to the given async mocks."""
    collected = []
    for mock in mocks:
        for call in mock.await_args_list:
            if call.args:
                collected.append(str(call.args[0]))
    return collected


def _callback_data(markup):
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


class _RecordingApp:
    """Minimal stand-in for ``telegram.ext.Application``.

    ``Application.add_handler`` refuses to run before ``initialize()`` (which
    performs network I/O), so the registration test records what ``setup_handlers``
    registers instead of building a live application.
    """

    def __init__(self):
        self.handlers = []
        self.error_handlers = []
        self.bot = SimpleNamespace(set_my_commands=AsyncMock())

    def add_handler(self, handler, group=0):
        self.handlers.append(handler)

    def add_error_handler(self, handler):
        self.error_handlers.append(handler)


class CommandRegistrationTests(TestCase):
    def test_every_teacher_command_is_registered_with_its_handler(self):
        app = _RecordingApp()
        handlers.setup_handlers(app)

        registered = {}
        for handler in app.handlers:
            if isinstance(handler, CommandHandler):
                for command in handler.commands:
                    registered[command] = handler

        for command, handler_name in TEACHER_COMMANDS.items():
            self.assertIn(command, registered, f"/{command} is not registered")
            self.assertIs(
                registered[command].callback,
                getattr(handlers, handler_name),
                f"/{command} is wired to the wrong callback",
            )

    def test_financial_bot_commands_refuse_group_chats(self):
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(type="group"),
            message=SimpleNamespace(reply_text=AsyncMock()),
            callback_query=None,
        )
        for handler in (
            handlers.mytuition_handler,
            handlers.course_payment_handler,
            handlers.payment_history_handler,
            handlers.payment_proof_handler,
            handlers.group_payments_handler,
            handlers.weekly_report_handler,
        ):
            with self.subTest(handler=handler.__name__):
                update.message.reply_text.reset_mock()
                async_to_sync(handler)(update, SimpleNamespace(args=[], user_data={}))
                update.message.reply_text.assert_awaited_once()
                self.assertIn(
                    "shaxsiy chatda", update.message.reply_text.await_args.args[0]
                )

    def test_command_menu_offers_the_teacher_commands(self):
        app = _RecordingApp()
        async_to_sync(handlers.post_init)(app)

        commands = app.bot.set_my_commands.await_args.args[0]
        names = [entry.command for entry in commands]
        for command in TEACHER_COMMANDS:
            self.assertIn(command, names)

    def test_help_mentions_private_course_tuition_command(self):
        update = SimpleNamespace(message=SimpleNamespace(reply_text=AsyncMock()))
        async_to_sync(handlers.help_handler)(update, SimpleNamespace())
        update.message.reply_text.assert_awaited_once()
        text = update.message.reply_text.await_args.args[0]
        self.assertIn("/mytuition", text)
        self.assertNotIn("/tuition_group", text)


class _BotFixture(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="bot-teacher@example.test",
            password="testpass123",
            role=User.Role.TEACHER,
            first_name="Oqituvchi",
            last_name="Karimov",
            telegram_chat_id=TEACHER_TG,
            telegram_identity_verified_at=timezone.now(),
        )
        self.other_teacher = User.objects.create_user(
            email="bot-other@example.test",
            password="testpass123",
            role=User.Role.TEACHER,
            first_name="Boshqa",
            last_name="Ustoz",
            telegram_chat_id=OTHER_TEACHER_TG,
            telegram_identity_verified_at=timezone.now(),
        )
        self.ali = User.objects.create_user(
            email="bot-ali@example.test",
            password="testpass123",
            role=User.Role.STUDENT,
            first_name="Ali",
            last_name="Valiyev",
        )
        self.zuhra = User.objects.create_user(
            email="bot-zuhra@example.test",
            password="testpass123",
            role=User.Role.STUDENT,
            first_name="Zuhra",
            last_name="Karimova",
        )
        self.gulnora = User.objects.create_user(
            email="bot-gulnora@example.test",
            password="testpass123",
            role=User.Role.STUDENT,
            first_name="Gulnora",
            last_name="Yusupova",
        )
        self.outsider = User.objects.create_user(
            email="bot-outsider@example.test",
            password="testpass123",
            role=User.Role.STUDENT,
            first_name="Begona",
            last_name="Oquvchi",
        )
        self.group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        self.group.students.add(self.ali, self.zuhra, self.gulnora)
        self.foreign_group = StudentGroup.objects.create(
            teacher=self.other_teacher,
            name="10-B",
        )
        self.foreign_group.students.add(self.outsider)
        self.context = SimpleNamespace(args=[], user_data={})

    # -- update factories ---------------------------------------------------

    def message_update(self, *, text="/groups", update_id=101, tg_id=TEACHER_TG):
        message = SimpleNamespace(text=text, reply_text=AsyncMock())
        update = SimpleNamespace(
            update_id=update_id,
            effective_user=SimpleNamespace(
                id=tg_id,
                first_name="T",
                last_name="U",
            ),
            message=message,
            callback_query=None,
        )
        return update, message

    def callback_update(self, data, *, update_id=201, tg_id=TEACHER_TG, query_id=900):
        query = SimpleNamespace(
            data=data,
            id=query_id,
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            message=SimpleNamespace(reply_text=AsyncMock()),
            from_user=SimpleNamespace(id=tg_id),
            bot=SimpleNamespace(send_message=AsyncMock()),
        )
        update = SimpleNamespace(
            update_id=update_id,
            effective_user=SimpleNamespace(
                id=tg_id,
                first_name="T",
                last_name="U",
            ),
            message=None,
            callback_query=query,
        )
        return update, query

    # -- drivers ------------------------------------------------------------

    def run_command(self, handler, *, text="/groups", update_id=101, tg_id=TEACHER_TG):
        update, message = self.message_update(
            text=text,
            update_id=update_id,
            tg_id=tg_id,
        )
        async_to_sync(handler)(update, self.context)
        return message

    def tap(self, data, *, update_id=201, tg_id=TEACHER_TG, query_id=900):
        update, query = self.callback_update(
            data,
            update_id=update_id,
            tg_id=tg_id,
            query_id=query_id,
        )
        async_to_sync(handlers.callback_handler)(update, self.context)
        return query

    def reply_texts(self, message):
        return _texts(message.reply_text)

    def callback_texts(self, query):
        return _texts(query.edit_message_text, query.message.reply_text)

    def joined(self, *mocks):
        return "\n".join(_texts(*mocks))

    def today_session(self):
        return AttendanceSession.objects.get(
            group=self.group,
            lesson_date=timezone.localdate(),
        )


class WeeklyReportCallbackTests(_BotFixture):
    def _report(self, group=None, *, summary=None):
        from apps.weekly_reports.models import WeeklyGroupReport

        start = timezone.now() - timedelta(days=7)
        return WeeklyGroupReport.objects.create(
            group=group or self.group,
            period_start=start,
            period_end=start + timedelta(days=6),
            period_label="2026-10-01 — 2026-10-07",
            summary=summary or {},
        )

    def test_teacher_can_open_private_academic_sections(self):
        report = self._report(
            summary={
                "attendance": {"active_students": 3, "present": 2},
                "essays": {"graded": 4, "average_raw_score": 18.5},
                "tests": {"completed_attempts": 5, "average_practice_percentage": 72.0},
            }
        )
        expectations = {
            "wr_att_": ("Davomat tafsilotlari", "Faol o'quvchilar: 3"),
            "wr_ess_": ("Esse natijalari", "Baholangan: 4"),
            "wr_tst_": ("Test natijalari", "Yakunlangan urinishlar: 5"),
            "wr_full_": ("to'liq hisobot", "Davomat"),
        }
        for index, (prefix, (heading, detail)) in enumerate(expectations.items()):
            with self.subTest(section=prefix):
                query = self.tap(f"{prefix}{report.pk}", query_id=1200 + index)
                text = self.joined(query.edit_message_text, query.message.reply_text)
                self.assertIn(heading, text)
                self.assertIn(detail, text)
                self.assertNotIn("student_id", text)

    def test_foreign_teacher_cannot_open_report(self):
        report = self._report(
            self.foreign_group,
            summary={
                "attendance": {"present": 7},
                "finance": {"outstanding_uzs": 99000},
            },
        )
        query = self.tap(f"wr_full_{report.pk}")
        text = self.joined(query.edit_message_text, query.message.reply_text)
        self.assertIn("Hisobot topilmadi yoki sizga tegishli emas", text)
        self.assertNotIn("10-B", text)
        self.assertNotIn("99000", text)

    def test_non_teacher_cannot_open_report(self):
        self.ali.telegram_chat_id = STUDENT_TG
        self.ali.telegram_identity_verified_at = timezone.now()
        self.ali.save(
            update_fields=["telegram_chat_id", "telegram_identity_verified_at"]
        )
        report = self._report(summary={"attendance": {"present": 3}})

        query = self.tap(f"wr_att_{report.pk}", tg_id=STUDENT_TG)
        text = self.joined(query.edit_message_text, query.message.reply_text)
        self.assertIn("huquqingiz yo'q", text.lower())
        self.assertNotIn("Keldi: 3", text)

    def test_finance_section_requires_explicit_permission(self):
        report = self._report(summary={"finance": {"outstanding_uzs": 123456}})
        query = self.tap(f"wr_fin_{report.pk}")
        text = self.joined(query.edit_message_text, query.message.reply_text)
        self.assertIn("Kurs to'lovlarini ko'rish huquqingiz yo'q", text)
        self.assertNotIn("123456", text)

    def test_platform_admin_can_view_finance_section(self):
        User.objects.create_user(
            email="bot-report-admin@example.test",
            password="testpass123",
            role=User.Role.ADMIN,
            telegram_chat_id=51000991,
            telegram_identity_verified_at=timezone.now(),
        )
        report = self._report(summary={"finance": {"outstanding_uzs": 123456}})
        query = self.tap(f"wr_fin_{report.pk}", tg_id=51000991)
        self.assertEqual(query.answer.await_count, 2)
        query.edit_message_text.assert_awaited_once()
        text = query.edit_message_text.await_args.args[0]
        self.assertIn("Kurs to'lovlari", text)
        self.assertIn("123456", text)


class TeacherCommandAuthorizationTests(_BotFixture):
    """The sender's Telegram identity resolves to the canonical account, and only
    a teacher (or platform admin) may read group data."""

    def test_groups_lists_only_the_teachers_own_groups(self):
        message = self.run_command(handlers.groups_handler)
        text = self.joined(message.reply_text)
        self.assertIn("Guruhlaringiz", text)
        self.assertIn("9-A", text)
        self.assertNotIn("10-B", text)
        self.assertNotIn("Begona Oquvchi", text)

        markup = message.reply_text.await_args.kwargs["reply_markup"]
        data = _callback_data(markup)
        self.assertIn(f"tgrp_{self.group.pk}", data)
        self.assertNotIn(f"tgrp_{self.foreign_group.pk}", data)

    def test_foreign_group_callback_is_refused(self):
        query = self.tap(f"tgrp_{self.foreign_group.pk}")
        text = self.joined(query.edit_message_text, query.message.reply_text)
        self.assertIn("Guruh topilmadi", text)
        self.assertNotIn("10-B", text)

    def test_student_account_is_refused_and_learns_nothing(self):
        self.ali.telegram_chat_id = STUDENT_TG
        self.ali.telegram_identity_verified_at = timezone.now()
        self.ali.save(
            update_fields=["telegram_chat_id", "telegram_identity_verified_at"],
        )

        for handler in (handlers.groups_handler, handlers.attendance_handler):
            message = self.run_command(handler, tg_id=STUDENT_TG)
            text = self.joined(message.reply_text)
            self.assertIn("faqat o'qituvchilar uchun", text)
            self.assertNotIn("9-A", text)

        # A refusal must not have side effects either.
        self.assertFalse(AttendanceSession.objects.exists())

    def test_unverified_telegram_link_is_handled_without_leaking(self):
        legacy = User.objects.create_user(
            email="bot-legacy@example.test",
            password=None,
            role=User.Role.TEACHER,
            first_name="Eski",
            last_name="Boglanish",
            telegram_chat_id=UNLINKED_TG,
            telegram_identity_verified_at=None,
        )
        StudentGroup.objects.create(teacher=legacy, name="11-A")

        message = self.run_command(handlers.groups_handler, tg_id=UNLINKED_TG)
        text = self.joined(message.reply_text)
        self.assertIn("Hisobni aniqlab bo'lmadi", text)
        self.assertNotIn("11-A", text)

    def test_unlinked_telegram_user_is_provisioned_as_a_student(self):
        message = self.run_command(handlers.groups_handler, tg_id=51000099)
        self.assertIn("faqat o'qituvchilar uchun", self.joined(message.reply_text))

        provisioned = User.objects.get(telegram_chat_id=51000099)
        self.assertEqual(provisioned.role, User.Role.STUDENT)

    def test_attendance_picker_offers_only_owned_groups(self):
        message = self.run_command(handlers.attendance_handler)
        self.assertIn(
            "Qaysi guruh uchun davomat olasiz?", self.joined(message.reply_text)
        )

        data = _callback_data(message.reply_text.await_args.kwargs["reply_markup"])
        self.assertIn(f"tatt_{self.group.pk}", data)
        self.assertNotIn(f"tatt_{self.foreign_group.pk}", data)


class AttendanceCallbackFlowTests(_BotFixture):
    """The register is created once, marked explicitly, and only finalized with a
    confirmation for anyone still unmarked."""

    def test_repeated_group_callback_creates_one_register(self):
        self.tap(f"tatt_{self.group.pk}", update_id=301)
        session = self.today_session()
        self.assertEqual(AttendanceSession.objects.filter(group=self.group).count(), 1)
        self.assertEqual(session.idempotency_key, f"tatt:{TEACHER_TG}:301")

        # Telegram may redeliver the same callback: same update id, same key.
        second = self.tap(f"tatt_{self.group.pk}", update_id=301, query_id=901)
        self.assertEqual(AttendanceSession.objects.filter(group=self.group).count(), 1)
        self.assertEqual(self.today_session().pk, session.pk)

        text = self.joined(second.edit_message_text, second.message.reply_text)
        self.assertIn("Belgilanmagan", text)
        self.assertIn("Ali Valiyev", text)

        markup = second.edit_message_text.await_args.kwargs["reply_markup"]
        data = _callback_data(markup)
        self.assertIn(f"tall_{session.pk}", data)
        self.assertIn(f"tfin_{session.pk}", data)
        self.assertIn(
            f"tmk_{session.pk}_{self.ali.pk}_{AttendanceRecord.Status.PRESENT}",
            data,
        )

    def test_marking_is_explicit_and_finalize_never_invents_absence(self):
        self.tap(f"tatt_{self.group.pk}", update_id=302)
        session = self.today_session()

        self.tap(f"tmk_{session.pk}_{self.ali.pk}_late", update_id=303, query_id=902)
        record = AttendanceRecord.objects.get(session=session, student=self.ali)
        self.assertEqual(record.status, AttendanceRecord.Status.LATE)
        self.assertEqual(record.marked_by, self.teacher)
        # Only the tapped student is recorded — nobody else was assumed absent.
        self.assertEqual(AttendanceRecord.objects.filter(session=session).count(), 1)
        self.assertEqual(
            session.records.filter(status=AttendanceRecord.Status.ABSENT).count(), 0
        )

        refusal = self.tap(f"tfin_{session.pk}", update_id=304, query_id=903)
        text = self.joined(refusal.edit_message_text, refusal.message.reply_text)
        self.assertIn("Davomat yakunlanmadi", text)
        self.assertIn("Zuhra Karimova", text)
        self.assertIn("Gulnora Yusupova", text)

        session.refresh_from_db()
        self.assertEqual(session.status, AttendanceSession.Status.DRAFT)
        self.assertEqual(AttendanceRecord.objects.filter(session=session).count(), 1)
        self.assertEqual(
            AttendanceRecord.objects.filter(
                session=session,
                status=AttendanceRecord.Status.ABSENT,
            ).count(),
            0,
        )

        confirmed = self.tap(f"tfinabs_{session.pk}", update_id=305, query_id=904)
        session.refresh_from_db()
        self.assertEqual(session.status, AttendanceSession.Status.FINALIZED)
        self.assertEqual(AttendanceRecord.objects.filter(session=session).count(), 3)
        self.assertEqual(
            AttendanceRecord.objects.get(session=session, student=self.ali).status,
            AttendanceRecord.Status.LATE,
        )
        self.assertEqual(
            AttendanceRecord.objects.filter(
                session=session,
                status=AttendanceRecord.Status.ABSENT,
            ).count(),
            2,
        )
        self.assertIn(
            "Davomat yakunlandi",
            self.joined(confirmed.edit_message_text, confirmed.message.reply_text),
        )

    def test_all_present_button_then_successful_finalize(self):
        self.tap(f"tatt_{self.group.pk}", update_id=306)
        session = self.today_session()

        self.tap(f"tall_{session.pk}", update_id=307, query_id=905)
        self.assertEqual(AttendanceRecord.objects.filter(session=session).count(), 3)
        self.assertEqual(
            AttendanceRecord.objects.filter(
                session=session,
                status=AttendanceRecord.Status.PRESENT,
            ).count(),
            3,
        )

        done = self.tap(f"tfin_{session.pk}", update_id=308, query_id=906)
        session.refresh_from_db()
        self.assertEqual(session.status, AttendanceSession.Status.FINALIZED)
        text = self.joined(done.edit_message_text, done.message.reply_text)
        self.assertIn("Davomat yakunlandi", text)
        self.assertIn("3 keldi", text)
        self.assertIn("0 kelmadi", text)

    def test_register_cannot_be_reopened_after_finalize(self):
        self.tap(f"tatt_{self.group.pk}", update_id=320)
        session = self.today_session()
        self.tap(f"tall_{session.pk}", update_id=321, query_id=920)
        self.tap(f"tfin_{session.pk}", update_id=322, query_id=921)

        again = self.tap(f"tatt_{self.group.pk}", update_id=323, query_id=922)
        self.assertIn(
            "allaqachon yakunlangan",
            self.joined(again.edit_message_text, again.message.reply_text),
        )
        self.assertEqual(self.today_session().pk, session.pk)

    def test_malformed_callbacks_are_ignored_without_touching_the_register(self):
        self.tap(f"tatt_{self.group.pk}", update_id=309)
        session = self.today_session()

        for index, data in enumerate(
            (
                "tmk_abc_def_present",
                f"tmk_{session.pk}_xyz_present",
                f"tmk_{session.pk}_{self.ali.pk}_bogus",
                "tmk_1_2_3_4",
            )
        ):
            query = self.tap(data, update_id=310, query_id=910 + index)
            # A malformed tap is dropped silently: no reply, no crash.
            self.assertEqual(query.edit_message_text.await_count, 0)
            self.assertEqual(query.message.reply_text.await_count, 0)

        self.assertEqual(AttendanceRecord.objects.filter(session=session).count(), 0)

    def test_foreign_session_callbacks_are_refused_and_change_nothing(self):
        foreign = create_session(
            group=self.foreign_group,
            teacher=self.other_teacher,
            actor=self.other_teacher,
        )[0]

        for index, data in enumerate(
            (
                f"tall_{foreign.pk}",
                f"tfin_{foreign.pk}",
                f"tfinabs_{foreign.pk}",
            )
        ):
            query = self.tap(data, update_id=311, query_id=930 + index)
            self.assertIn(
                "sizga tegishli emas",
                self.joined(query.edit_message_text, query.message.reply_text),
            )

        foreign.refresh_from_db()
        self.assertEqual(foreign.status, AttendanceSession.Status.DRAFT)
        self.assertEqual(AttendanceRecord.objects.filter(session=foreign).count(), 0)

    def test_foreign_and_unknown_group_callbacks_are_refused(self):
        for index, data in enumerate(
            (
                f"tatt_{self.foreign_group.pk}",
                "tatt_999999",
            )
        ):
            query = self.tap(data, update_id=312, query_id=940 + index)
            text = self.joined(query.edit_message_text, query.message.reply_text)
            self.assertIn("Guruh topilmadi", text)
            self.assertNotIn("10-B", text)

        self.assertEqual(AttendanceSession.objects.count(), 0)


class ReportAndPrivacyTests(_BotFixture):
    """Teacher reports carry real counts and never leak another group's students."""

    def _essay_setup(self):
        topic = EssayTopic.objects.create(
            title="Kitobxonlik",
            description="d",
            created_by=self.teacher,
        )
        assignment = EssayAssignment.objects.create(
            topic=topic,
            group=self.group,
            assigned_by=self.teacher,
        )
        common = {
            "topic": topic,
            "assignment": assignment,
            "essay_text": "Matn " * 60,
            "max_score": 24,
            "submitted_at": timezone.now(),
        }
        EssaySubmission.objects.create(
            student=self.ali,
            status=EssaySubmission.Status.GRADED,
            total_score=20,
            **common,
        )
        EssaySubmission.objects.create(
            student=self.zuhra,
            status=EssaySubmission.Status.PENDING,
            total_score=0,
            **common,
        )
        return topic, assignment

    def test_essay_results_header_counts_and_paging(self):
        self._essay_setup()

        query = self.tap(f"ters_{self.group.pk}")
        text = self.joined(query.edit_message_text, query.message.reply_text)
        self.assertIn("Baholangan: *1*", text)
        self.assertIn("Kutilmoqda: *1*", text)
        self.assertIn("Topshirilmagan: *1*", text)
        self.assertIn("Ali Valiyev", text)
        self.assertIn("Zuhra Karimova", text)
        self.assertNotIn("10-B", text)
        self.assertNotIn("Begona Oquvchi", text)

        beyond = self.tap(f"tersp_{self.group.pk}_1000", query_id=950)
        self.assertIn(
            "Ko'rsatilgan: 0 / 2",
            self.joined(beyond.edit_message_text, beyond.message.reply_text),
        )

        pending_only = self.tap(f"terspend_{self.group.pk}", query_id=951)
        pending_text = self.joined(
            pending_only.edit_message_text,
            pending_only.message.reply_text,
        )
        self.assertIn("Zuhra Karimova", pending_text)
        self.assertNotIn("Ali Valiyev", pending_text)

    def test_attendance_report_is_aggregate_only(self):
        session, _ = create_session(
            group=self.group,
            teacher=self.teacher,
            actor=self.teacher,
        )
        mark(session, self.ali, AttendanceRecord.Status.PRESENT, actor=self.teacher)

        query = self.tap(f"trpt_{self.group.pk}")
        text = self.joined(query.edit_message_text, query.message.reply_text)
        # An unfinished register must not read as a full absence.
        self.assertIn(
            "Yakunlanmagan davomat darslari kelmaganlik deb hisoblanmaydi.", text
        )
        self.assertIn("1 yakunlanmagan", text)
        for name in ("Ali Valiyev", "Zuhra Karimova", "Gulnora Yusupova"):
            self.assertNotIn(name, text)

        finalized = finalize(session, actor=self.teacher, mark_unmarked_as_absent=True)
        self.assertTrue(finalized["ok"])

        after = self.tap(f"trpt_{self.group.pk}", query_id=952)
        after_text = self.joined(after.edit_message_text, after.message.reply_text)
        # The counts are markdown-bold, so the literal has to include the markup.
        self.assertIn("Darslar: *1* yakunlangan", after_text)
        self.assertIn("❌ Kelmadi (sababsiz): *2*", after_text)
        for name in ("Ali Valiyev", "Zuhra Karimova", "Gulnora Yusupova"):
            self.assertNotIn(name, after_text)

    def test_group_report_has_counts_and_no_student_names(self):
        self._essay_setup()

        query = self.tap(f"tgreport_{self.group.pk}")
        text = self.joined(query.edit_message_text, query.message.reply_text)
        self.assertIn("guruh hisoboti", text)
        self.assertIn("Davomat:", text)
        self.assertIn("Baholangan: *1*", text)
        self.assertIn("Kutilmoqda: *1*", text)
        for name in ("Ali Valiyev", "Zuhra Karimova", "Gulnora Yusupova"):
            self.assertNotIn(name, text)

    def test_students_command_lists_the_roster_with_percentages(self):
        picker = self.run_command(handlers.students_handler)
        self.assertIn("Qaysi guruh o'quvchilari?", self.joined(picker.reply_text))

        roster = self.tap(f"tstu_{self.group.pk}")
        text = self.joined(roster.edit_message_text, roster.message.reply_text)
        self.assertIn("9-A", text)
        self.assertIn("Ali Valiyev", text)
        self.assertIn("Zuhra Karimova", text)
        self.assertIn("davomat:", text)
        self.assertNotIn("10-B", text)
        self.assertNotIn("Begona Oquvchi", text)

    def test_group_report_command_offers_only_owned_groups(self):
        picker = self.run_command(handlers.group_report_handler)
        self.assertIn("Qaysi guruh hisoboti?", self.joined(picker.reply_text))

        data = _callback_data(picker.reply_text.await_args.kwargs["reply_markup"])
        self.assertIn(f"tgreport_{self.group.pk}", data)
        self.assertNotIn(f"tgreport_{self.foreign_group.pk}", data)
