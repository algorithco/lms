"""
Teacher CRM Bot Handlers & Callbacks (Module 3).
Interactive attendance toggles, tuition reports, reminders, and receipt verification.
"""

from __future__ import annotations

import logging
from typing import Any
from django.utils import timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from apps.accounts.models import User
from apps.courses.models import StudentGroup, GroupEnrollment
from apps.groups.services import (
    get_teacher_groups,
    get_group_finance_summary,
    send_debtor_payment_reminders,
    save_interactive_attendance,
    record_tuition_payment,
    send_telegram_safe,
)

logger = logging.getLogger(__name__)


def build_davomat_keyboard(
    group_id: int, students: list[Any], statuses: dict[int, str]
) -> InlineKeyboardMarkup:
    """
    Build 1-click toggle buttons:
      🟢 Alisher V. | 🔴 Sardor K. | 🟢 Madina T.
    Plus action buttons:
      [ ✅ Barchasi keldi ] | [ 💾 Saqlash ]
    """
    keyboard = []
    row = []
    for st in students:
        st_id = st.id
        status = statuses.get(st_id, "present")
        emoji = "🟢" if status == "present" else "🔴"
        name_parts = (st.get_full_name() or st.email).split()
        short_name = (
            f"{name_parts[0]} {name_parts[1][0]}."
            if len(name_parts) > 1
            else name_parts[0][:12]
        )
        btn_text = f"{emoji} {short_name}"
        row.append(
            InlineKeyboardButton(
                btn_text,
                callback_data=f"dav_tog_{group_id}_{st_id}",
            )
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Action buttons
    keyboard.append(
        [
            InlineKeyboardButton(
                "✅ Barchasi keldi", callback_data=f"dav_all_{group_id}"
            ),
            InlineKeyboardButton("💾 Saqlash", callback_data=f"dav_save_{group_id}"),
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton("🔙 Guruhlar", callback_data="dav_groups"),
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def build_tolovlar_text(summary: dict[str, Any]) -> str:
    """Format tuition financial summary."""
    g_name = summary.get("group_name", "Guruh")
    tot_st = summary.get("total_students", 0)
    paid_cnt = summary.get("paid_count", 0)
    debt_cnt = summary.get("debtor_count", 0)
    coll_str = f"{summary.get('collected_amount', 0):,.0f} so'm".replace(",", " ")
    pend_str = f"{summary.get('pending_amount', 0):,.0f} so'm".replace(",", " ")

    lines = [
        "💳 <b>KURS TO'LOVLARI HISOBOTI (CRM)</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"👥 Guruh: <b>{g_name}</b>",
        f"🎓 Jami o'quvchilar: <b>{tot_st} ta</b>",
        f"🟢 To'laganlar: <b>{paid_cnt} ta</b> ({coll_str})",
        f"🔴 Qarzdorlar: <b>{debt_cnt} ta</b> ({pend_str})",
        "━━━━━━━━━━━━━━━━━━",
    ]

    debtors = summary.get("debtors", [])
    if debtors:
        lines.append("⚠️ <b>Qarzdorlar ro'yxati:</b>")
        for idx, d in enumerate(debtors[:15], 1):
            fee_str = f"{d['fee']:,.0f} so'm".replace(",", " ")
            lines.append(
                f"{idx}. <b>{d['student_name']}</b> — {fee_str} ({d['next_due']})"
            )
    else:
        lines.append("🎉 Ushbu guruhda barcha to'lovlar 100% to'langan!")

    return "\n".join(lines)


def build_tolovlar_keyboard(group_id: int | None = None) -> InlineKeyboardMarkup:
    """Action buttons for tuition overview."""
    cb = f"crm_remind_grp_{group_id}" if group_id else "crm_remind_all_debtors"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📢 Qarzdorlarga eslatma yuborish", callback_data=cb
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 Yangilash", callback_data=f"crm_refresh_tolov_{group_id or 0}"
                )
            ],
        ]
    )


def build_receipt_approval_prompt(
    student_name: str, group_name: str, amount: float | int, enrollment_id: int
) -> tuple[str, InlineKeyboardMarkup]:
    """Generate prompt and buttons for teacher to approve/reject student receipt."""
    amt_str = f"{amount:,.0f} so'm".replace(",", " ")
    text = (
        "📥 <b>Yangi to'lov cheki keldi!</b>\n\n"
        f"👤 O'quvchi: <b>{student_name}</b>\n"
        f"👥 Guruh: <b>{group_name}</b>\n"
        f"💰 Aniqlangan summa: <b>{amt_str}</b>\n\n"
        "Ushbu to'lovni tasdiqlaysizmi?"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Tasdiqlash",
                    callback_data=f"rcpt_appr_{enrollment_id}_{int(amount)}",
                ),
                InlineKeyboardButton(
                    "❌ Rad etish", callback_data=f"rcpt_rej_{enrollment_id}"
                ),
            ]
        ]
    )
    return text, keyboard


# ---------------------------------------------------------------------------
# Telegram Handlers
# ---------------------------------------------------------------------------


async def davomat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /davomat — Ustozlar uchun tezkor interaktiv davomat tizimi.
    Guruhdagi o'quvchilar ro'yxati 🟢 Keldi | 🔴 Kelmadi tugmalari bilan chiqadi.
    """
    if not update.effective_user or not update.message:
        return

    from asgiref.sync import sync_to_async

    user = await sync_to_async(
        lambda: User.objects.filter(telegram_chat_id=update.effective_user.id).first()
    )()
    if not user:
        await update.message.reply_text(
            "⚠️ Telegram hisobingiz tizimga bog'lanmagan. Avval saytga kirib yoki /start orqali hisobingizni ulang."
        )
        return

    if (
        user.role not in (User.Role.TEACHER, User.Role.ADMIN)
        and not user.is_staff
        and not user.is_superuser
    ):
        await update.message.reply_text(
            "ℹ️ <b>/davomat</b> buyrug'i faqat o'qituvchilar va markaz ma'murlari uchun mo'ljallangan.",
            parse_mode="HTML",
        )
        return

    groups = await sync_to_async(get_teacher_groups)(user)
    if not groups:
        await update.message.reply_text(
            "🏫 Sizga hali guruh biriktirilmagan. Guruh yaratish yoki biriktirish uchun ma'muriyatga murojaat qiling."
        )
        return

    # Agar 1 ta guruh bo'lsa, to'g'ridan-to'g'ri interaktiv davomat
    if len(groups) == 1:
        target_group = groups[0]
        students = await sync_to_async(
            lambda: list(
                target_group.students.filter(is_active=True).order_by(
                    "first_name", "last_name"
                )
            )
        )()
        if not students:
            await update.message.reply_text(
                f"ℹ️ <b>{target_group.name}</b> guruhida hozircha o'quvchilar yo'q.",
                parse_mode="HTML",
            )
            return

        statuses_key = f"dav_statuses_{target_group.id}"
        statuses = context.user_data.get(statuses_key, {})
        for st in students:
            if st.id not in statuses:
                statuses[st.id] = "present"
        context.user_data[statuses_key] = statuses

        today_str = timezone.localdate().strftime("%d.%m.%Y")
        text = (
            "🗓 <b>TEZKOR INTERAKTIV DAVOMAT</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👥 Guruh: <b>{target_group.name}</b>\n"
            f"📅 Sana: <b>{today_str}</b>\n\n"
            "<i>O'quvchi ustiga bosib 'Keldi (🟢)' yoki 'Kelmadi (🔴)' holatiga o'tkazing, so'ngra '💾 Saqlash' tugmasini bosing:</i>"
        )
        kb = build_davomat_keyboard(target_group.id, students, statuses)
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
        return

    # Ko'p guruh bo'lsa, tanlash klaviaturasi
    buttons = [
        [InlineKeyboardButton(f"🏫 {g.name}", callback_data=f"dav_grp_{g.id}")]
        for g in groups
    ]
    await update.message.reply_text(
        "🗓 <b>Qaysi guruh uchun davomat olasiz?</b>\nKerakli guruhni tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def tolovlar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /tolovlar — Ustozlar uchun oylik kurs to'lovlari hisoboti va qarzdorlar nazorati.
    """
    if not update.effective_user or not update.message:
        return

    from asgiref.sync import sync_to_async

    user = await sync_to_async(
        lambda: User.objects.filter(telegram_chat_id=update.effective_user.id).first()
    )()
    if not user:
        await update.message.reply_text(
            "⚠️ Telegram hisobingiz tizimga bog'lanmagan. Avval /start orqali profilingizni ulang."
        )
        return

    if (
        user.role not in (User.Role.TEACHER, User.Role.ADMIN)
        and not user.is_staff
        and not user.is_superuser
    ):
        await update.message.reply_text(
            "ℹ️ <b>/tolovlar</b> buyrug'i faqat ustozlar uchun mo'ljallangan.",
            parse_mode="HTML",
        )
        return

    groups = await sync_to_async(get_teacher_groups)(user)
    if not groups:
        await update.message.reply_text("🏫 Sizga guruh biriktirilmagan.")
        return

    if len(groups) == 1:
        summary = await sync_to_async(get_group_finance_summary)(groups[0])
        text = build_tolovlar_text(summary)
        kb = build_tolovlar_keyboard(groups[0].id)
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
        return

    # Ko'p guruh bo'lsa, umumiy yig'ma hisobot
    total_st = 0
    total_coll = 0
    total_pend = 0
    total_debtors = 0
    all_debtors = []

    for g in groups:
        s = await sync_to_async(get_group_finance_summary)(g)
        total_st += s.get("total_students", 0)
        total_coll += s.get("collected_amount", 0)
        total_pend += s.get("pending_amount", 0)
        total_debtors += s.get("debtor_count", 0)
        for d in s.get("debtors", []):
            d["group_name"] = g.name
            all_debtors.append(d)

    coll_str = f"{total_coll:,.0f} so'm".replace(",", " ")
    pend_str = f"{total_pend:,.0f} so'm".replace(",", " ")

    lines = [
        "💳 <b>BARCHA GURUHLAR BO'YICHA TO'LOVLAR (CRM)</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"👥 Guruhlar soni: <b>{len(groups)} ta</b>",
        f"🎓 Jami o'quvchilar: <b>{total_st} ta</b>",
        f"🟢 Yig'ilgan tushum: <b>{coll_str}</b>",
        f"🔴 Qarzdorlik: <b>{pend_str}</b> ({total_debtors} nafar)",
        "━━━━━━━━━━━━━━━━━━",
    ]
    if all_debtors:
        lines.append("⚠️ <b>Qarzdorlar ro'yxati:</b>")
        for idx, d in enumerate(all_debtors[:12], 1):
            fee_s = f"{d['fee']:,.0f} so'm".replace(",", " ")
            lines.append(
                f"{idx}. <b>{d['student_name']}</b> ({d.get('group_name', '')}) — {fee_s}"
            )
    else:
        lines.append("🎉 Barcha guruhlarda to'lovlar 100% qilingan!")

    kb = build_tolovlar_keyboard(None)
    await update.message.reply_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=kb
    )


async def handle_crm_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
) -> None:
    """Dispatch and process all CRM, Davomat, and Receipt verification callbacks."""
    query = update.callback_query
    if not query:
        return

    from asgiref.sync import sync_to_async

    # 1. dav_groups — Guruhlar ro'yxatini ko'rsatish
    if data == "dav_groups":
        user = await sync_to_async(
            lambda: User.objects.filter(
                telegram_chat_id=update.effective_user.id
            ).first()
        )()
        groups = await sync_to_async(get_teacher_groups)(user) if user else []
        buttons = [
            [InlineKeyboardButton(f"🏫 {g.name}", callback_data=f"dav_grp_{g.id}")]
            for g in groups
        ]
        await query.edit_message_text(
            "🗓 <b>Qaysi guruh uchun davomat olasiz?</b>\nKerakli guruhni tanlang:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    # 2. dav_grp_<id> — Tanlangan guruh uchun interaktiv davomatni ochish
    if data.startswith("dav_grp_"):
        try:
            group_id = int(data.split("_")[2])
        except (IndexError, ValueError):
            return
        target_group = await sync_to_async(
            lambda: StudentGroup.objects.filter(id=group_id).first()
        )()
        if target_group:
            students = await sync_to_async(
                lambda: list(
                    target_group.students.filter(is_active=True).order_by(
                        "first_name", "last_name"
                    )
                )
            )()
            statuses_key = f"dav_statuses_{target_group.id}"
            statuses = context.user_data.get(statuses_key, {})
            for st in students:
                if st.id not in statuses:
                    statuses[st.id] = "present"
            context.user_data[statuses_key] = statuses
            today_str = timezone.localdate().strftime("%d.%m.%Y")
            text = (
                "🗓 <b>TEZKOR INTERAKTIV DAVOMAT</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👥 Guruh: <b>{target_group.name}</b>\n"
                f"📅 Sana: <b>{today_str}</b>\n\n"
                "<i>O'quvchi ustiga bosib 'Keldi (🟢)' yoki 'Kelmadi (🔴)' holatiga o'tkazing, so'ngra '💾 Saqlash' tugmasini bosing:</i>"
            )
            kb = build_davomat_keyboard(target_group.id, students, statuses)
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        return

    # 3. dav_tog_<group_id>_<student_id> — 1-klikli toggle (🟢 <-> 🔴)
    if data.startswith("dav_tog_"):
        parts = data[len("dav_tog_") :].split("_")
        try:
            group_id, student_id = int(parts[0]), int(parts[1])
            target_group = await sync_to_async(
                lambda: StudentGroup.objects.filter(id=group_id).first()
            )()
            if target_group:
                students = await sync_to_async(
                    lambda: list(
                        target_group.students.filter(is_active=True).order_by(
                            "first_name", "last_name"
                        )
                    )
                )()
                statuses_key = f"dav_statuses_{group_id}"
                statuses = context.user_data.get(statuses_key, {})
                curr = statuses.get(student_id, "present")
                statuses[student_id] = "absent" if curr == "present" else "present"
                context.user_data[statuses_key] = statuses
                today_str = timezone.localdate().strftime("%d.%m.%Y")
                text = (
                    "🗓 <b>TEZKOR INTERAKTIV DAVOMAT</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"👥 Guruh: <b>{target_group.name}</b>\n"
                    f"📅 Sana: <b>{today_str}</b>\n\n"
                    "<i>O'quvchi ustiga bosib 'Keldi (🟢)' yoki 'Kelmadi (🔴)' holatiga o'tkazing, so'ngra '💾 Saqlash' tugmasini bosing:</i>"
                )
                kb = build_davomat_keyboard(group_id, students, statuses)
                await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            logger.warning("dav_tog error: %s", e)
        return

    # 4. dav_all_<group_id> — Hammasini keldi deb belgilash
    if data.startswith("dav_all_"):
        try:
            group_id = int(data.split("_")[2])
        except (IndexError, ValueError):
            return
        target_group = await sync_to_async(
            lambda: StudentGroup.objects.filter(id=group_id).first()
        )()
        if target_group:
            students = await sync_to_async(
                lambda: list(
                    target_group.students.filter(is_active=True).order_by(
                        "first_name", "last_name"
                    )
                )
            )()
            statuses_key = f"dav_statuses_{group_id}"
            statuses = {st.id: "present" for st in students}
            context.user_data[statuses_key] = statuses
            today_str = timezone.localdate().strftime("%d.%m.%Y")
            text = (
                "🗓 <b>TEZKOR INTERAKTIV DAVOMAT</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👥 Guruh: <b>{target_group.name}</b>\n"
                f"📅 Sana: <b>{today_str}</b>\n\n"
                "<i>Barcha o'quvchilar 'Keldi (🟢)' deb belgilandi. Saqlash uchun '💾 Saqlash' ni bosing:</i>"
            )
            kb = build_davomat_keyboard(group_id, students, statuses)
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        return

    # 5. dav_save_<group_id> — Davomatni bazaga saqlash va ota-onalarga avto-eslatma
    if data.startswith("dav_save_"):
        try:
            group_id = int(data.split("_")[2])
        except (IndexError, ValueError):
            return
        user = await sync_to_async(
            lambda: User.objects.filter(
                telegram_chat_id=update.effective_user.id
            ).first()
        )()
        target_group = await sync_to_async(
            lambda: StudentGroup.objects.filter(id=group_id).first()
        )()
        if target_group and user:
            statuses_key = f"dav_statuses_{group_id}"
            statuses = context.user_data.get(statuses_key, {})
            sess, stats = await sync_to_async(save_interactive_attendance)(
                target_group, user, statuses
            )
            today_str = timezone.localdate().strftime("%d.%m.%Y")
            await query.edit_message_text(
                f"✅ <b>{target_group.name} davomati muvaffaqiyatli saqlandi!</b>\n\n"
                f"📅 Sana: <b>{today_str}</b>\n"
                f"👥 Jami: <b>{stats['total']} nafar</b>\n"
                f"🟢 Keldi: <b>{stats['present']} nafar</b>\n"
                f"🔴 Kelmadi: <b>{stats['absent']} nafar</b>\n\n"
                "<i>Kelmagan o'quvchilarning ota-onalariga Telegram orqali avtomatik xabarnoma yuborildi.</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🔙 Boshqa guruh", callback_data="dav_groups"
                            )
                        ]
                    ]
                ),
            )
        return

    # 6. crm_remind_ — Qarzdorlarga eslatma yuborish
    if data == "crm_remind_all_debtors" or data.startswith("crm_remind_grp_"):
        grp_id = None
        if data.startswith("crm_remind_grp_"):
            try:
                grp_id = int(data.split("_")[3])
            except (IndexError, ValueError):
                grp_id = None

        user = await sync_to_async(
            lambda: User.objects.filter(
                telegram_chat_id=update.effective_user.id
            ).first()
        )()
        if user:
            res = await sync_to_async(send_debtor_payment_reminders)(user, grp_id)
            tot = res.get("total_notified", 0)
            await query.answer(f"✅ {tot} nafar eslatma yuborildi!", show_alert=True)
            await query.message.reply_text(
                "✅ <b>To'lov eslatmalari yuborildi!</b>\n\n"
                f"Jami <b>{tot} nafar</b> o'quvchi va ularning ota-onalariga Telegram orqali muloyim eslatma xabari yetkazildi.",
                parse_mode="HTML",
            )
        return

    # 7. rcpt_appr_<enrollment_id>_<amount> — Ustoz to'lov chekini tasdiqlashi
    if data.startswith("rcpt_appr_"):
        parts = data[len("rcpt_appr_") :].split("_")
        try:
            enrollment_id, amount = int(parts[0]), int(parts[1])
            enrollment = await sync_to_async(
                lambda: (
                    GroupEnrollment.objects.select_related("student", "group")
                    .filter(id=enrollment_id)
                    .first()
                )
            )()
            if enrollment:
                await sync_to_async(record_tuition_payment)(enrollment, amount)
                due_str = enrollment.next_payment_due.strftime("%d.%m.%Y")
                await query.edit_message_text(
                    f"✅ <b>To'lov tasdiqlandi!</b>\n\n"
                    f"👤 O'quvchi: <b>{enrollment.student.get_full_name()}</b>\n"
                    f"👥 Guruh: <b>{enrollment.group.name}</b>\n"
                    f"💰 Summa: <b>{amount:,.0f} so'm</b>\n"
                    f"📅 Yangi to'lov muddati: <b>{due_str}</b> gacha uzaytirildi.",
                    parse_mode="HTML",
                )
                if enrollment.student.telegram_chat_id:
                    st_msg = (
                        "✅ <b>Ustozingiz to'lov chekingizni tasdiqladi!</b>\n\n"
                        f"👥 Guruh: <b>{enrollment.group.name}</b>\n"
                        f"💰 Qabul qilingan summa: <b>{amount:,.0f} so'm</b>\n"
                        f"📅 Keyingi to'lov sanangiz: <b>{due_str}</b> gacha uzaytirildi.\n\n"
                        "Rahmat, darslaringizda omad tilaymiz!"
                    )
                    await sync_to_async(send_telegram_safe)(
                        enrollment.student.telegram_chat_id, st_msg
                    )
        except Exception as e:
            logger.warning("rcpt_appr error: %s", e)
        return

    # 8. rcpt_rej_<enrollment_id> — Ustoz to'lov chekini rad etishi
    if data.startswith("rcpt_rej_"):
        try:
            enrollment_id = int(data.split("_")[2])
            enrollment = await sync_to_async(
                lambda: (
                    GroupEnrollment.objects.select_related("student", "group")
                    .filter(id=enrollment_id)
                    .first()
                )
            )()
            if enrollment:
                await query.edit_message_text(
                    f"❌ <b>To'lov cheki rad etildi.</b>\n\n"
                    f"👤 O'quvchi: <b>{enrollment.student.get_full_name()}</b>\n"
                    f"👥 Guruh: <b>{enrollment.group.name}</b>",
                    parse_mode="HTML",
                )
                if enrollment.student.telegram_chat_id:
                    rej_msg = (
                        "❌ <b>To'lov chekingiz ustozingiz tomonidan rad etildi.</b>\n\n"
                        f"👥 Guruh: <b>{enrollment.group.name}</b>\n\n"
                        "Iltimos, to'lov chekini qayta tekshirib yuboring yoki ustozingiz bilan bog'laning."
                    )
                    await sync_to_async(send_telegram_safe)(
                        enrollment.student.telegram_chat_id, rej_msg
                    )
        except Exception as e:
            logger.warning("rcpt_rej error: %s", e)
        return
