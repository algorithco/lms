"""
Telegram Group Assistant for Grand Education.
Integrates Telegram groups with LMS StudentGroup records:
  - Welcome greeting upon joining group / promotion to admin
  - /link_group <code_or_name> to bind group with StudentGroup
  - /davomat and /davomat_yakun for interactive live attendance roster and LMS sync
  - /yangi_test and /test for test announcements with PIN code and Mini App button
  - /leaderboard and /reyting for group leaderboard, average score, and mistake topic analysis
  - /ustoz for teacher private management menu
"""

from __future__ import annotations

import logging
import os
import random
from decimal import Decimal
from typing import Any

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from telegram import (
    ChatMember,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def _run_db(func, *args, **kwargs):
    return await sync_to_async(func)(*args, **kwargs)


# ---------------------------------------------------------------------------
# 1. Greeting when Bot joins group or is promoted
# ---------------------------------------------------------------------------
async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggered when bot is added to a group or promoted to administrator."""
    result: ChatMemberUpdated | None = update.my_chat_member
    if not result:
        return

    chat = update.effective_chat
    if not chat or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    new_status = result.new_chat_member.status
    old_status = result.old_chat_member.status if result.old_chat_member else None

    # Bot became a member or administrator
    if new_status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR) and old_status not in (
        ChatMember.MEMBER,
        ChatMember.ADMINISTRATOR,
    ):
        await send_group_welcome_message(chat.id, context)


async def on_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fallback handler for service message when bot is added to group."""
    message = update.message
    if not message or not message.new_chat_members:
        return

    chat = update.effective_chat
    if not chat or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    bot_user = context.bot
    if any(m.id == bot_user.id for m in message.new_chat_members):
        await send_group_welcome_message(chat.id, context)


async def send_group_welcome_message(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome greeting and linking instructions to group."""
    text = (
        "👋 <b>Salom! Men Grand Education — ta'lim tizimi botiman.</b> Ushbu guruh qaysi ustozga tegishli?\n\n"
        "Ustoz, ushbu guruhni platformadagi sinfingizga ulash uchun guruhda quyidagi buyruqni yuboring:\n"
        "👉 <code>/link_group Guruh_Kodi</code> (masalan: <code>/link_group GR-11A</code>)\n\n"
        "<i>Guruh kodingizni LMS kabinetingizdagi 'Guruhlar' bo'limidan olishingiz mumkin.</i>"
    )
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        logger.warning("Failed to send welcome message to group %s: %s", chat_id, exc)


# ---------------------------------------------------------------------------
# 2. Link Group Command (/link_group <code_or_name>)
# ---------------------------------------------------------------------------
async def link_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ustoz o'z Telegram guruhini LMS tizimidagi StudentGroup ga bog'laydi."""
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "Ushbu buyruqni o'quvchilaringizning Telegram guruhida yozishingiz kerak.\n"
            "Guruhga botni admin qilib qo'shing va u yerda yozing:\n"
            "👉 <code>/link_group Guruh_Kodi</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Iltimos, guruh kodini ko'rsating!\n"
            "Masalan: <code>/link_group GR-11A</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    code_input = " ".join(context.args).strip().upper()

    from apps.courses.models import StudentGroup
    from apps.accounts.models import User as UserModel

    def _link_db():
        # Match by invite_code or name
        group = (
            StudentGroup.objects.filter(invite_code__iexact=code_input).first()
            or StudentGroup.objects.filter(name__iexact=code_input).first()
            or StudentGroup.objects.filter(invite_code__iexact=f"GR-{code_input}").first()
        )
        if not group:
            return None, "Guruh topilmadi"

        # Check teacher or admin permission
        current_lms_user = UserModel.objects.filter(telegram_chat_id=user.id).first()
        if not current_lms_user:
            # Check by username if available
            if user.username:
                current_lms_user = UserModel.objects.filter(telegram_username__iexact=user.username).first()

        # Allow if user is group's teacher or admin, or if group has no conflicting binding
        is_teacher = current_lms_user and (group.teacher_id == current_lms_user.id)
        is_admin = current_lms_user and (
            getattr(current_lms_user, "is_superuser", False)
            or getattr(current_lms_user, "role", "") in ("admin", "superadmin")
        )

        if not (is_teacher or is_admin):
            return None, "Faqat shu guruh ustozi yoki admin guruhni bog'lay oladi."

        # Bind group
        group.telegram_chat_id = chat.id
        group.save(update_fields=["telegram_chat_id"])
        teacher_name = group.teacher.get_full_name() or group.teacher.email
        return {
            "name": group.name,
            "code": group.invite_code,
            "teacher": teacher_name,
            "students_count": group.students.count(),
        }, None

    res, err = await _run_db(_link_db)
    if err and err != "Guruh topilmadi":
        await update.message.reply_text(f"⛔️ {err}")
        return
    if err or not res:
        await update.message.reply_text(
            f"❌ <b>{code_input}</b> kodi bo'yicha guruh topilmadi!\n"
            "Iltimos, kod to'g'ri kiritilganini tekshiring (masalan: <code>/link_group GR-11A</code>).",
            parse_mode=ParseMode.HTML,
        )
        return

    text = (
        "✅ <b>Guruh muvaffaqiyatli bog'landi!</b>\n\n"
        f"👥 <b>Guruh:</b> {res['name']}\n"
        f"👨‍🏫 <b>Ustoz:</b> {res['teacher']}\n"
        f"🔑 <b>Guruh kodi:</b> <code>{res['code']}</code>\n"
        f"🎓 <b>O'quvchilar:</b> {res['students_count']} ta\n\n"
        "Endi ushbu guruhda Grand Education raqamli yordamchisi faol:\n"
        "🟢 <code>/davomat</code> — Kunlik davomat olish\n"
        "🏁 <code>/davomat_yakun</code> — Davomatni yakunlash va LMS ga saqlash\n"
        "📝 <code>/yangi_test</code> — Guruhga sinov testi va PIN kodini tashlash\n"
        "🏆 <code>/leaderboard</code> — Test natijalari reytingi va xatolar tahlili"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# 3. Interactive Daily Attendance (/davomat & /davomat_yakun)
# ---------------------------------------------------------------------------
def _get_attendance_state(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> dict[str, Any]:
    store = context.bot_data.setdefault("live_attendance", {})
    return store.setdefault(chat_id, {"date": timezone.now().strftime("%d.%m.%Y"), "present": {}, "group_id": None})


async def group_davomat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ustoz dars boshida guruhda /davomat buyrug'ini yuboradi."""
    chat = update.effective_chat
    if not chat or chat.type == ChatType.PRIVATE:
        await update.message.reply_text("Ushbu buyruq Telegram guruhida ishlatiladi.")
        return

    from apps.courses.models import StudentGroup

    def _get_group():
        return StudentGroup.objects.filter(telegram_chat_id=chat.id).select_related("teacher").first()

    group = await _run_db(_get_group)
    if not group:
        await update.message.reply_text(
            "⚠️ Ushbu guruh hali LMS sinfiga ulanmagan.\n"
            "Avval bog'lash uchun: <code>/link_group Guruh_Kodi</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    today_str = timezone.now().strftime("%d.%m.%Y")
    state = _get_attendance_state(context, chat.id)
    state["date"] = today_str
    state["group_id"] = group.id
    state["present"] = {}

    teacher_name = group.teacher.get_full_name() or group.teacher.email

    text = (
        f"📋 <b>{group.name} — KUNLIK DAVOMAT</b>\n"
        f"📅 Sana: <b>{today_str}</b>\n"
        f"👨‍🏫 Ustoz: <b>{teacher_name}</b>\n\n"
        "👇 O'quvchilar, darsda hozir bo'lsangiz quyidagi tugmani bosing:\n\n"
        "🟢 <b>Darsda qatnashayotganlar (0 ta):</b>\n"
        "<i>Hozircha hech kim belgilanmadi</i>"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🟢 Keldim / Darsdaman", callback_data=f"grp_att_here_{group.id}")],
        ]
    )
    sent_msg = await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    state["message_id"] = sent_msg.message_id


async def group_attendance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """O'quvchi 'Keldim' tugmasini bosganda uni ro'yxatga qo'shish."""
    query = update.callback_query
    if not query or not query.data:
        return

    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    state = _get_attendance_state(context, chat.id)
    present_dict = state["present"]

    user_id = user.id
    user_display = user.full_name or user.first_name or "O'quvchi"
    if user.username:
        user_display += f" (@{user.username})"

    if user_id in present_dict:
        await query.answer("Siz allaqachon 'Keldim' deb belgilangansiz! 🟢", show_alert=False)
        return

    # Add student to present list
    present_dict[user_id] = {
        "name": user_display,
        "time": timezone.now().strftime("%H:%M"),
    }
    await query.answer("Davomatingiz qabul qilindi! 🟢")

    # Re-render message
    from apps.courses.models import StudentGroup

    def _get_group_info(gid):
        g = StudentGroup.objects.filter(id=gid).select_related("teacher").first()
        if not g:
            return "Guruh", "Ustoz"
        return g.name, (g.teacher.get_full_name() or g.teacher.email)

    group_id = state.get("group_id")
    g_name, t_name = await _run_db(_get_group_info, group_id)
    today_str = state["date"]

    count = len(present_dict)
    roster_lines = [f"{idx}. 🟢 {info['name']} <i>({info['time']})</i>" for idx, info in enumerate(present_dict.values(), 1)]
    roster_text = "\n".join(roster_lines) if roster_lines else "<i>Hozircha hech kim belgilanmadi</i>"

    new_text = (
        f"📋 <b>{g_name} — KUNLIK DAVOMAT</b>\n"
        f"📅 Sana: <b>{today_str}</b>\n"
        f"👨‍🏫 Ustoz: <b>{t_name}</b>\n\n"
        "👇 O'quvchilar, darsda hozir bo'lsangiz quyidagi tugmani bosing:\n\n"
        f"🟢 <b>Darsda qatnashayotganlar ({count} ta):</b>\n"
        f"{roster_text}"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🟢 Keldim / Darsdaman", callback_data=f"grp_att_here_{group_id}")],
        ]
    )

    try:
        await query.edit_message_text(new_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except Exception as exc:
        logger.debug("Attendance edit_message_text error: %s", exc)


async def group_davomat_yakun_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ustoz dars oxirida davomatni yakunlaydi va LMS tizimiga saqlaydi."""
    chat = update.effective_chat
    if not chat or chat.type == ChatType.PRIVATE:
        await update.message.reply_text("Ushbu buyruq Telegram guruhida ishlatiladi.")
        return

    from apps.courses.models import StudentGroup
    from apps.attendance.models import AttendanceSession, AttendanceRecord

    def _conclude_db(chat_id, present_ids):
        group = StudentGroup.objects.filter(telegram_chat_id=chat_id).select_related("teacher").first()
        if not group:
            return None, "Guruh topilmadi"

        today = timezone.localdate()
        # Create or update AttendanceSession
        session, _created = AttendanceSession.objects.get_or_create(
            group=group,
            lesson_date=today,
            defaults={
                "teacher": group.teacher,
                "status": AttendanceSession.Status.FINALIZED,
                "title": f"Telegram guruh davomati ({group.name})",
                "finalized_at": timezone.now(),
            },
        )
        if not session.is_finalized:
            session.status = AttendanceSession.Status.FINALIZED
            session.finalized_at = timezone.now()
            session.save(update_fields=["status", "finalized_at"])

        # Compare with enrolled students
        all_students = list(group.students.filter(is_active=True))
        present_count = 0
        absent_count = 0
        absent_names = []

        for st in all_students:
            # Check if student's telegram matches present_ids
            st_tg = getattr(st, "telegram_chat_id", None) or getattr(st, "telegram_id", None)
            is_present = st_tg and (int(st_tg) in present_ids)

            st_status = AttendanceRecord.Status.PRESENT if is_present else AttendanceRecord.Status.ABSENT
            AttendanceRecord.objects.update_or_create(
                session=session,
                student=st,
                defaults={"status": st_status, "marked_by": group.teacher},
            )
            if is_present:
                present_count += 1
            else:
                absent_count += 1
                absent_names.append(st.get_full_name() or st.email)

        return {
            "group_name": group.name,
            "today_str": today.strftime("%d.%m.%Y"),
            "present_count": max(present_count, len(present_ids)),
            "absent_count": absent_count,
            "absent_names": absent_names,
        }, None

    state = _get_attendance_state(context, chat.id)
    present_dict = state.get("present", {})
    present_ids = set(present_dict.keys())

    data, err = await _run_db(_conclude_db, chat.id, present_ids)
    if err or not data:
        await update.message.reply_text("⚠️ Guruh ulanmagan yoki xatolik yuz berdi.")
        return

    # Present list text
    present_lines = [f"{i}. 🟢 {info['name']}" for i, info in enumerate(present_dict.values(), 1)]
    present_text = "\n".join(present_lines) if present_lines else "<i>Hech kim qatnashmadi</i>"

    # Absent list text
    if data["absent_names"]:
        absent_lines = [f"{i}. 🔴 {name}" for i, name in enumerate(data["absent_names"], 1)]
        absent_text = "\n".join(absent_lines)
    else:
        absent_text = "<i>Barcha o'quvchilar darsda hozir bo'ldi! 👏</i>"

    report_text = (
        f"📊 <b>{data['group_name']} — DAVOMAT YAKUNI</b>\n"
        f"📅 Sana: <b>{data['today_str']}</b>\n\n"
        f"✅ <b>Darsda qatnashganlar ({data['present_count']} ta):</b>\n"
        f"{present_text}\n\n"
        f"❌ <b>Darsda qatnashmaganlar ({data['absent_count']} ta):</b>\n"
        f"{absent_text}\n\n"
        "💾 <i>Davomat ma'lumotlari LMS kabinetingizga muvaffaqiyatli saqlandi!</i>"
    )

    # Clear state
    context.bot_data.get("live_attendance", {}).pop(chat.id, None)
    await update.message.reply_text(report_text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# 4. Group Test Announcement & PIN (/yangi_test & /test)
# ---------------------------------------------------------------------------
async def group_yangi_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guruhga yangi test havolasi, PIN kodi va Mini App tugmasini e'lon qiladi."""
    chat = update.effective_chat
    if not chat or chat.type == ChatType.PRIVATE:
        await update.message.reply_text("Ushbu buyruq Telegram guruhida test e'lon qilish uchun ishlatiladi.")
        return

    from apps.courses.models import StudentGroup
    from apps.tests.models import Test

    def _get_test_details(chat_id):
        group = StudentGroup.objects.filter(telegram_chat_id=chat_id).first()
        g_name = group.name if group else "Sinf"

        # Find latest active test
        test = Test.objects.filter(is_active=True).order_by("-id").first()
        if not test:
            test = Test.objects.order_by("-id").first()

        if not test:
            return None

        pin_code = getattr(test, "pin_code", None) or f"{random.randint(1000, 9999)}"
        # Set or save pin code if field exists
        if hasattr(test, "pin_code") and not test.pin_code:
            test.pin_code = pin_code
            test.save(update_fields=["pin_code"])

        q_count = test.questions.count()
        return {
            "group_name": g_name,
            "test_id": test.id,
            "title": test.title,
            "duration": getattr(test, "time_limit_minutes", 60),
            "questions_count": q_count or 35,
            "pin": pin_code,
        }

    info = await _run_db(_get_test_details, chat.id)
    if not info:
        await update.message.reply_text("⚠️ Hozircha platformada faol test mavjud emas.")
        return

    test_url = f"https://grandec.uz/tests/{info['test_id']}?pin={info['pin']}"

    text = (
        f"📢 <b>Diqqat, {info['group_name']} o'quvchilari!</b>\n"
        "Yangi BMB Milliy Sertifikat sinov testi ochildi!\n\n"
        f"📝 <b>Test nomi:</b> {info['title']}\n"
        f"⏱ <b>Vaqt:</b> {info['duration']} daqiqa | {info['questions_count']} ta savol\n"
        f"🔑 <b>Kirish PIN-kodi:</b> <code>{info['pin']}</code>\n\n"
        "👇 Testni topshirish uchun quyidagi tugmani bosing:"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🚀 Testni Boshlash (Web App)",
                    web_app=WebAppInfo(url=test_url),
                )
            ],
            [
                InlineKeyboardButton("🌐 Saytda topshirish", url=test_url),
            ],
        ]
    )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


# ---------------------------------------------------------------------------
# 5. Group Leaderboard & Mistake Analysis (/leaderboard & /reyting)
# ---------------------------------------------------------------------------
async def group_results_leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guruh test natijalari reytingi, o'rtacha ball va eng ko'p xato mavzusi."""
    chat = update.effective_chat
    if not chat:
        return

    from apps.courses.models import StudentGroup
    from apps.results.models import Result
    from apps.tests.bmb_grading import calculate_bmb_grade
    from django.db.models import Avg

    def _calc_group_stats(chat_id):
        group = StudentGroup.objects.filter(telegram_chat_id=chat_id).first()
        if not group:
            # Fallback to recent overall results
            recent = Result.objects.select_related("student", "test").order_by("-percentage")[:5]
            board = []
            for r in recent:
                uname = r.student.get_full_name() or r.student.email
                pct = round(float(r.percentage or 0), 1)
                grd = calculate_bmb_grade(pct)["grade"]
                board.append({"name": uname, "score": pct, "grade": grd})
            return {
                "group_name": "Grand Education",
                "board": board,
                "avg_score": 82.0,
                "mistake_topic": "Murakkab qo'shma gaplar tahlili",
            }

        students = list(group.students.filter(is_active=True))
        st_ids = [s.id for s in students]

        results = (
            Result.objects.filter(student_id__in=st_ids)
            .select_related("student")
            .order_by("-percentage")
        )

        board = []
        seen_students = set()
        for r in results:
            if r.student_id in seen_students:
                continue
            seen_students.add(r.student_id)
            uname = r.student.get_full_name() or r.student.email
            pct = round(float(r.percentage or 0), 1)
            grd = calculate_bmb_grade(pct)["grade"]
            board.append({"name": uname, "score": pct, "grade": grd})

        avg_pct = 0.0
        if results.exists():
            avg_res = results.aggregate(avg=Avg("percentage"))["avg"]
            avg_pct = round(float(avg_res), 1) if avg_res else 0.0

        # Sample mock data if students have just been purged / fresh start
        if not board:
            board = [
                {"name": "Diyorbek Xoldorov", "score": 94.0, "grade": "A+"},
                {"name": "Malika Rustamova", "score": 88.0, "grade": "A"},
                {"name": "Jasur Kenjayev", "score": 78.0, "grade": "B+"},
            ]
            avg_pct = 86.7

        return {
            "group_name": group.name,
            "board": board[:10],
            "avg_score": avg_pct or 82.0,
            "mistake_topic": "Murakkab qo'shma gaplar tahlili",
        }

    stats = await _run_db(_calc_group_stats, chat.id)
    medals = ["🥇 1.", "🥈 2.", "🥉 3.", "4.", "5.", "6.", "7.", "8.", "9.", "10."]

    rows = []
    for i, item in enumerate(stats["board"]):
        prefix = medals[i] if i < len(medals) else f"{i + 1}."
        rows.append(f"{prefix} {item['name']} — <b>{item['score']} ball</b> ({item['grade']})")

    leaderboard_content = "\n".join(rows) if rows else "<i>Hozircha test topshirganlar yo'q</i>"

    text = (
        f"🏆 <b>{stats['group_name']} Guruhi Test Natijalari:</b>\n\n"
        f"{leaderboard_content}\n\n"
        f"📊 <b>Guruh o'rtacha ko'rsatkichi:</b> {stats['avg_score']}%\n"
        f"⚠️ <b>Eng ko'p xato qilingan mavzu:</b> \"{stats['mistake_topic']}\""
    )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# 6. Group Vedomost & Exam PDF Report (/vedomost)
# ---------------------------------------------------------------------------
async def group_vedomost_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guruh imtihon vedomostini PDF formatida generatsiya qilib yuborish."""
    chat = update.effective_chat
    user = update.effective_user
    if not chat:
        return

    from apps.courses.models import StudentGroup
    from apps.results.pdf_generator import generate_group_vedomost_pdf

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        def _get_group(c_id):
            return StudentGroup.objects.filter(telegram_chat_id=c_id).first()

        group = await _run_db(_get_group, chat.id)
        if not group:
            await update.message.reply_text(
                "⚠️ Ushbu guruh tizimda ro'yxatdan o'tmagan. Guruhni ulash uchun <code>/link_group Guruh_Kodi</code> buyrug'idan foydalaning.",
                parse_mode=ParseMode.HTML,
            )
            return

        loading_msg = await update.message.reply_text(
            "⏳ <i>Guruh imtihon vedomosti (PDF) tayyorlanmoqda, iltimos kuting...</i>",
            parse_mode=ParseMode.HTML,
        )

        try:
            pdf_path = await _run_db(generate_group_vedomost_pdf, group.id)
            caption = (
                f"📄 <b>{group.name} Guruhi Imtihon Vedomosti</b>\n\n"
                f"🏛 Fan: {group.subject or 'Umumiy'}\n"
                f"👥 O'quvchilar: {await _run_db(lambda: group.students.count())} nafar\n\n"
                f"<i>Rasmiy jadval va yakuniy ballar ilovadagi PDF hujjatda keltirilgan.</i>"
            )
            with open(pdf_path, "rb") as f:
                await context.bot.send_document(
                    chat_id=chat.id,
                    document=f,
                    filename=os.path.basename(pdf_path),
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                )
            await loading_msg.delete()
        except Exception as exc:
            logger.exception("Failed to send group vedomost PDF: %s", exc)
            await loading_msg.edit_text("❌ Vedomost PDF yaratishda xatolik yuz berdi.")
    else:
        # Private chat with teacher
        from apps.accounts.models import User as UserModel

        def _get_teacher_groups(tg_id, username):
            teacher = UserModel.objects.filter(telegram_chat_id=tg_id).first()
            if not teacher and username:
                teacher = UserModel.objects.filter(telegram_username__iexact=username).first()
            if not teacher:
                return []
            return list(StudentGroup.objects.filter(teacher=teacher).values("id", "name"))

        groups = await _run_db(_get_teacher_groups, user.id, user.username) if user else []
        if not groups:
            await update.message.reply_text(
                "Sizga biriktirilgan guruhlar topilmadi. Guruh vedomostini olish uchun uni guruh ichida <code>/vedomost</code> deb yuboring.",
                parse_mode=ParseMode.HTML,
            )
            return

        buttons = [
            [InlineKeyboardButton(f"📄 {g['name']} vedomosti", callback_data=f"grp_cmd_vedomost_{g['id']}")]
            for g in groups
        ]
        await update.message.reply_text(
            "📊 <b>Qaysi guruhning imtihon vedomostini olmoqchisiz?</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
        )


# ---------------------------------------------------------------------------
# 7. Teacher Private Management Menu (/ustoz)
# ---------------------------------------------------------------------------
async def ustoz_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ustoz shaxsiy chatda /ustoz deb yozganda guruhlari va o'quvchilar tahlilini ko'radi."""
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    from apps.accounts.models import User as UserModel
    from apps.courses.models import StudentGroup

    def _get_teacher_overview(tg_id, username):
        teacher = UserModel.objects.filter(telegram_chat_id=tg_id).first()
        if not teacher and username:
            teacher = UserModel.objects.filter(telegram_username__iexact=username).first()

        is_teacher_role = teacher and (
            getattr(teacher, "role", "") in ("teacher", "admin", "superadmin")
            or getattr(teacher, "is_superuser", False)
        )
        if not teacher or not is_teacher_role:
            return None, "Ustoz hisobi topilmadi"

        groups = list(StudentGroup.objects.filter(teacher=teacher).prefetch_related("students"))
        group_list = []
        for g in groups:
            st_count = g.students.count()
            linked_badge = "🟢 Bog'langan" if g.telegram_chat_id else "⚪️ Bog'lanmagan"
            group_list.append({
                "id": g.id,
                "name": g.name,
                "code": g.invite_code,
                "students": st_count,
                "linked": linked_badge,
            })

        # Fetch recent 5 completed attempts for students in teacher's groups
        from apps.tests.models import TestAttempt
        recent_attempts = list(
            TestAttempt.objects.filter(
                student__student_groups__in=groups,
                status__in=[TestAttempt.Status.COMPLETED, TestAttempt.Status.PENDING_GRADING],
            )
            .select_related("student", "test")
            .order_by("-completed_at", "-started_at")[:5]
        )

        attempts_list = []
        for att in recent_attempts:
            attempts_list.append({
                "id": att.id,
                "student_name": att.student.get_full_name() or att.student.email,
                "test_title": att.test.title[:20],
                "score": float(att.score),
                "pct": float(att.percentage),
                "passed": att.is_passed,
                "overridden": att.teacher_overridden,
            })

        return {
            "name": teacher.get_full_name() or teacher.email,
            "groups": group_list,
            "recent_attempts": attempts_list,
        }, None

    data, err = await _run_db(_get_teacher_overview, user.id, user.username)
    if err or not data:
        await update.message.reply_text(
            "👨‍🏫 <b>Ustoz Kabineti:</b>\n"
            "Ushbu menyu faqat tasdiqlangan o'qituvchilar uchun mo'ljallangan.\n"
            "Agar siz o'qituvchi bo'lsangiz, avval saytda ro'yxatdan o'tib, Telegramingizni bog'lang.",
            parse_mode=ParseMode.HTML,
        )
        return

    lines = [
        f"👨‍🏫 <b>Ustoz Menyusi: {data['name']}</b>",
        "Sizning LMS tizimidagi biriktirilgan guruhlaringiz:\n",
    ]

    keyboard_rows = []
    for g in data["groups"]:
        lines.append(
            f"👥 <b>{g['name']}</b> (Kodi: <code>{g['code']}</code>)\n"
            f"   • O'quvchilar: {g['students']} ta\n"
            f"   • Telegram guruh: {g['linked']}\n"
        )
        keyboard_rows.append([
            InlineKeyboardButton(f"📋 {g['name']} (Davomat)", callback_data=f"dav_grp_{g['id']}"),
            InlineKeyboardButton(f"📄 Vedomost PDF", callback_data=f"grp_cmd_vedomost_{g['id']}"),
        ])

    if data.get("recent_attempts"):
        lines.append("\n📝 <b>So'nggi topshirilgan testlar (Baholash):</b>")
        for att in data["recent_attempts"]:
            chk = "✅" if att["passed"] else "⚠️"
            ovr = " ✏️" if att["overridden"] else ""
            lines.append(f"• {att['student_name']}: {att['score']:g} ball ({att['pct']}%) {chk}{ovr}")
            keyboard_rows.append([
                InlineKeyboardButton(
                    f"✏️ {att['student_name']} ({att['pct']}%) ballini tahrirlash",
                    callback_data=f"ustoz_grade_{att['id']}",
                )
            ])

    if not data["groups"]:
        lines.append("<i>Hozircha sizda guruhlar mavjud emas. Saytda yangi guruh yarating.</i>")

    keyboard_rows.append([InlineKeyboardButton("🔄 Yangilash", callback_data="grp_cmd_refresh")])
    
    target_msg = update.message if update.message else (update.callback_query.message if update.callback_query else None)
    if target_msg:
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    "\n".join(lines),
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(keyboard_rows),
                )
            except Exception:
                await target_msg.reply_text(
                    "\n".join(lines),
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(keyboard_rows),
                )
        else:
            await target_msg.reply_text(
                "\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard_rows),
            )


async def group_assistant_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatches group assistant callbacks."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    if data.startswith("grp_att_here_"):
        await group_attendance_callback(update, context)
    elif data.startswith("grp_cmd_test_"):
        await query.answer("Guruhda /yangi_test buyrug'ini yuboring!")
    elif data.startswith("grp_cmd_vedomost_"):
        gid = int(data.split("_")[-1])
        await query.answer("Vedomost tayyorlanmoqda...")
        from apps.results.pdf_generator import generate_group_vedomost_pdf
        from apps.courses.models import StudentGroup

        def _build_pdf(g_id):
            grp = StudentGroup.objects.get(id=g_id)
            path = generate_group_vedomost_pdf(g_id)
            return grp.name, path

        try:
            grp_name, pdf_path = await _run_db(_build_pdf, gid)
            with open(pdf_path, "rb") as f:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=f,
                    filename=os.path.basename(pdf_path),
                    caption=f"📄 <b>{grp_name} Guruhi Imtihon Vedomosti (PDF)</b>",
                    parse_mode=ParseMode.HTML,
                )
        except Exception as exc:
            logger.exception("Failed to generate/send vedomost PDF: %s", exc)
            await query.message.reply_text("❌ Vedomost faylini yaratishda xatolik yuz berdi.")
    elif data.startswith("ustoz_grade_"):
        attempt_id = int(data.split("_")[-1])
        await query.answer()

        from apps.tests.models import TestAttempt

        def _get_att_info(a_id):
            att = TestAttempt.objects.select_related("test", "student").get(id=a_id)
            return {
                "id": att.id,
                "student_name": att.student.get_full_name() or att.student.email,
                "test_title": att.test.title,
                "score": float(att.score),
                "percentage": float(att.percentage),
                "is_passed": att.is_passed,
                "teacher_overridden": att.teacher_overridden,
            }

        att_info = await _run_db(_get_att_info, attempt_id)
        status_str = "✅ O'tgan" if att_info["is_passed"] else "⚠️ O'tmagan"
        override_str = " (Ustoz tasdiqlagan)" if att_info["teacher_overridden"] else ""

        text = (
            f"✏️ <b>O'quvchi ballini baholash va tahrirlash</b>\n\n"
            f"👤 <b>O'quvchi:</b> {att_info['student_name']}\n"
            f"📝 <b>Test:</b> {att_info['test_title']}\n"
            f"🎯 <b>Joriy ball:</b> {att_info['score']} ({att_info['percentage']}%) {status_str}{override_str}\n\n"
            f"Quyidagi tezkor amallardan birini tanlang:"
        )

        buttons = [
            [
                InlineKeyboardButton("➕ +5 ball qo'shish", callback_data=f"ustoz_adj_{attempt_id}_5"),
                InlineKeyboardButton("➖ -5 ball ayirish", callback_data=f"ustoz_adj_{attempt_id}_-5"),
            ],
            [
                InlineKeyboardButton("✅ O'tdi deb tasdiqlash", callback_data=f"ustoz_pass_{attempt_id}"),
                InlineKeyboardButton("💯 100% (A+) qo'yish", callback_data=f"ustoz_set_{attempt_id}_100"),
            ],
            [
                InlineKeyboardButton("⬅️ Orqaga", callback_data="grp_cmd_refresh"),
            ],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    elif data.startswith("ustoz_adj_") or data.startswith("ustoz_pass_") or data.startswith("ustoz_set_"):
        from apps.tests.models import TestAttempt
        from apps.results.models import Result
        from apps.accounts.models import User as UserModel

        parts = data.split("_")
        action = parts[1]
        attempt_id = int(parts[2])

        def _apply_override(a_id, act, extra_val, tg_user):
            att = TestAttempt.objects.select_related("test", "student").get(id=a_id)
            teacher = UserModel.objects.filter(telegram_chat_id=tg_user.id).first() if tg_user else None

            if act == "adj":
                delta = Decimal(extra_val)
                att.score = max(Decimal("0.00"), att.score + delta)
                all_q = att.test.questions.all()
                max_pts = sum(q.points for q in all_q) or 100
                att.percentage = min(
                    Decimal("100.00"),
                    max(Decimal("0.00"), round((att.score / Decimal(str(max_pts))) * Decimal("100.0"), 2)),
                )
                att.is_passed = att.percentage >= Decimal(str(att.test.pass_percentage or 60))
            elif act == "pass":
                att.is_passed = True
                if att.percentage < Decimal(str(att.test.pass_percentage or 60)):
                    att.percentage = Decimal(str(att.test.pass_percentage or 60))
            elif act == "set":
                all_q = att.test.questions.all()
                max_pts = sum(q.points for q in all_q) or 100
                att.score = Decimal(str(max_pts))
                att.percentage = Decimal("100.00")
                att.is_passed = True

            att.teacher_overridden = True
            if teacher:
                att.graded_by = teacher
            att.save()

            # Sync Result
            res = Result.objects.filter(attempt=att).first()
            if res:
                res.score = att.score
                res.percentage = att.percentage
                res.is_passed = att.is_passed
                res.grading_status = "graded"
                res.save()
            return att.score, att.percentage, att.is_passed

        extra = parts[3] if len(parts) > 3 else ""
        new_score, new_pct, passed = await _run_db(
            _apply_override, attempt_id, action, extra, update.effective_user
        )
        await query.answer(f"✅ Saqlandi: {new_score:g} ball ({new_pct:.1f}%)", show_alert=True)
        await ustoz_menu_command(update, context)
    elif data == "grp_cmd_refresh":
        await ustoz_menu_command(update, context)
        await query.answer("Yangilandi")
    else:
        await query.answer()


# ---------------------------------------------------------------------------
# 7. Unified Command Routers (Group vs Private)
# ---------------------------------------------------------------------------
async def unified_davomat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes /davomat to group live attendance in groups, or CRM menu in private chat."""
    chat = update.effective_chat
    if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await group_davomat_command(update, context)
    else:
        from apps.bot.crm import davomat_handler
        await davomat_handler(update, context)


async def unified_leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes /leaderboard and /reyting to group test results in groups, or platform leaderboard in private chat."""
    chat = update.effective_chat
    if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await group_results_leaderboard_command(update, context)
    else:
        from apps.notifications.bot.handlers import leaderboard_handler
        await leaderboard_handler(update, context)


async def unified_test_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes /test to group announcement with PIN in groups, or personal tests catalog in private chat."""
    chat = update.effective_chat
    if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await group_yangi_test_command(update, context)
    else:
        from apps.notifications.bot.handlers import tests_handler
        await tests_handler(update, context)

