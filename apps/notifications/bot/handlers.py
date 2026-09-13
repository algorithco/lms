"""
Telegram Bot Handlers — interactive commands for uz_essaygrader bot.

Commands:
    /start    — Welcome + auto-link telegram_chat_id
    /help     — Bot commands help
    /profile  — User stats (tests, essays, XP, certificates)
    /tests    — Available tests list
    /results  — Recent test results
    /essays   — Essay topics

Inline Keyboards:
    - Main menu actions
    - Test list navigation
    - Essay topic selection
"""
from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING

import telegram
from asgiref.sync import sync_to_async
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_or_create_user(update: Update) -> "User | None":
    """Get or create a user using only Telegram's immutable numeric ID."""
    from apps.accounts.services.telegram_identity import get_or_create_telegram_user
    from apps.accounts.services.telegram_identity import TelegramIdentityUnverified

    tg_user = update.effective_user
    if not tg_user:
        return None
    try:
        user, created = get_or_create_telegram_user({
            "id": tg_user.id,
            "first_name": tg_user.first_name or "",
            "last_name": tg_user.last_name or "",
        })
    except TelegramIdentityUnverified:
        logger.warning("Legacy Telegram identity requires verification: tg_id=%d", tg_user.id)
        return None
    if created:
        logger.info("Bot: new user registered: tg_id=%d, user_id=%d", tg_user.id, user.id)
    return user if user.is_active else None


# Async wrapper — allows sync Django ORM calls inside async handlers
_get_or_create_user_async = sync_to_async(_get_or_create_user)


async def _run_db(func, *args, **kwargs):
    """Run a synchronous Django DB operation from async context.

    Usage:
        results = await _run_db(lambda: list(Result.objects.filter(student=user)))
        count = await _run_db(Result.objects.filter(student=user).count)
    """
    return await sync_to_async(func)(*args, **kwargs)


async def send_reply(update: Update, text: str, **kwargs):
    """Send a reply that works from both message and callback query contexts.

    Note: Does NOT call query.answer() — the caller should handle that.
    Safety: if query.message is None (old/deleted message), falls back to
    sending a new message via bot.send_message.
    """
    if update.message:
        return await update.message.reply_text(text, **kwargs)
    elif update.callback_query:
        query = update.callback_query
        if query.message:
            return await query.message.reply_text(text, **kwargs)
        else:
            # Message too old or deleted — send new message to user
            return await query.bot.send_message(
                chat_id=query.from_user.id,
                text=text,
                **kwargs,
            )


async def edit_or_reply(update: Update, text: str, **kwargs):
    """Edit callback message if available, otherwise reply."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            return await query.edit_message_text(text, **kwargs)
        except Exception:
            return await query.message.reply_text(text, **kwargs)
    elif update.message:
        return await update.message.reply_text(text, **kwargs)


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu inline keyboard."""
    from django.conf import settings as _settings
    _site_url = getattr(_settings, "SITE_URL", "http://localhost:8000")
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Testlar", callback_data="menu_tests"),
            InlineKeyboardButton("✍️ Esse", callback_data="menu_essays"),
        ],
        [
            InlineKeyboardButton("📊 Natijalarim", callback_data="menu_results"),
            InlineKeyboardButton("👤 Profilim", callback_data="menu_profile"),
        ],
        [
            InlineKeyboardButton("🏆 Reyting", callback_data="menu_leaderboard"),
            InlineKeyboardButton("🔥 Streak", callback_data="menu_streak"),
        ],
        [
            InlineKeyboardButton("⚔️ Arena (1v1)", callback_data="menu_arena"),
            InlineKeyboardButton("📋 Kunlik vazifalar", callback_data="menu_daily"),
        ],
        [
            InlineKeyboardButton("💎 Premium", callback_data="menu_premium"),
        ],
        [
            InlineKeyboardButton("📱 Test topshirish (TMA)", web_app={"url": f"{_site_url}/tma/"}),
        ],
        [
            InlineKeyboardButton("🌐 Web'da ochish", url=f"{_site_url}/dashboard/"),
        ],
    ])


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command — welcome + auto-link + auth token support."""
    args = context.args if context.args else []

    if args and args[0].startswith("link_"):
        from apps.accounts.services.telegram_link import confirm_link_challenge
        tg_user = update.effective_user
        state = (
            await _run_db(confirm_link_challenge, args[0].removeprefix("link_"), tg_user.id)
            if tg_user else "invalid"
        )
        messages = {
            "confirmed": "✅ Telegram hisobingiz veb profilingizga bog'landi.",
            "conflict": "❌ Bu Telegram ID boshqa hisobga bog'langan. Administratorga murojaat qiling.",
            "expired": "⏰ Bog'lash havolasining muddati tugagan. Vebda yangisini oling.",
            "invalid": "❌ Bog'lash havolasi noto'g'ri yoki ishlatilgan.",
        }
        await update.message.reply_text(messages[state])
        return

    # --- Auth token flow: /start auth_<token> ---
    if args and args[0].startswith("auth_"):
        await _handle_auth_token(update, context, args[0])
        return

    # --- Normal /start flow ---
    user = await _get_or_create_user_async(update)
    if not user:
        await update.message.reply_text("Xatolik yuz berdi. Qayta urinib ko'ring.")
        return

    welcome = (
        f"Salom, *{user.first_name}*! 👋\n\n"
        f"🎓 *Ona Tili & Adabiyot* — Ona tili va Adabiyot bo'yicha ta'lim platformasi.\n\n"
        f"Bu yerda:\n"
        f"• 📝 Testlarni topshirishingiz\n"
        f"• ✍️ Esse yozishingiz (AI baholaydi)\n"
        f"• 📊 Natijalaringizni ko'rishingiz mumkin\n\n"
        f"Quyidagi tugmalardan foydalaning 👇"
    )

    await update.message.reply_text(
        welcome,
        parse_mode="Markdown",
        reply_markup=_main_menu_keyboard(),
    )


async def _handle_auth_token(update: Update, context: ContextTypes.DEFAULT_TYPE, token_arg: str) -> None:
    """Handle /start auth_<token> — start conversation to collect name & phone."""
    from apps.notifications.models import TelegramAuthToken

    token = token_arg.removeprefix("auth_")
    tg_user = update.effective_user

    if not tg_user:
        await update.message.reply_text("Xatolik: Telegram foydalanuvchi aniqlanmadi.")
        return

    try:
        auth_token = await _run_db(TelegramAuthToken.objects.get, token=token)
    except TelegramAuthToken.DoesNotExist:
        await update.message.reply_text(
            "❌ Noto'g'ri yoki eskirgan token.\n\n"
            "Iltimos, veb-saytda qaytadan 'Telegram orqali kirish' tugmasini bosing."
        )
        return

    if auth_token.is_expired:
        await update.message.reply_text(
            "⏰ Token muddati tugagan (10 daqiqa).\n\n"
            "Iltimos, veb-saytda qaytadan 'Telegram orqali kirish' tugmasini bosing."
        )
        return

    if auth_token.consumed_at or auth_token.is_verified:
        await update.message.reply_text(
            "❌ Bu token allaqachon ishlatilgan.\n\n"
            "Iltimos, veb-saytda qaytadan 'Telegram orqali kirish' tugmasini bosing."
        )
        return

    # Store token in context for conversation flow
    context.user_data["auth_token"] = token
    context.user_data["auth_state"] = "awaiting_name"

    # Start conversation: ask for full name
    await update.message.reply_text(
        "🔐 *Telegram orqali kirish*\n\n"
        "Iltimos, to'liq ism-familiyangizni kiriting:\n"
        "(Masalan: Ali Karimov)",
        parse_mode="Markdown",
    )

    logger.info("TG auth conversation started: tg_id=%d", tg_user.id if tg_user else 0)


async def auth_conversation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages during Telegram auth conversation.

    States:
        awaiting_name  → user sends their full name
        awaiting_phone → user sends their phone number → generate code
    """
    from django.utils import timezone
    from apps.notifications.models import TelegramAuthToken

    auth_state = context.user_data.get("auth_state")
    if not auth_state or auth_state == "idle":
        return  # Not in auth conversation — ignore

    auth_token_str = context.user_data.get("auth_token")
    if not auth_token_str:
        return

    text = (update.message.text or "").strip()
    tg_user = update.effective_user

    if auth_state == "awaiting_name":
        if update.message.contact:
            await update.message.reply_text("Iltimos, avval ism-familiyangizni kiriting.")
            return
        if len(text) < 3 or len(text) > 100:
            await update.message.reply_text("Iltimos, to'liq ism-familiyani kiriting (3-100 belgi).")
            return

        # Save name and ask for phone — offer verified share-contact button
        context.user_data["auth_name"] = text
        context.user_data["auth_state"] = "awaiting_phone"

        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton(text="📱 Telefonni yuborish", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await update.message.reply_text(
            f"✅ Ism: {text}\n\n"
            "Endi telefon raqamingizni tasdiqlash uchun tugmani bosing.",
            reply_markup=keyboard,
        )

    elif auth_state == "awaiting_phone":
        # Prefer verified contact if shared via Telegram button
        import re as _re

        contact = getattr(update.message, "contact", None)
        if contact and contact.phone_number:
            # Enforce one true number: only Telegram-verified contact is accepted
            if not contact.user_id or contact.user_id != tg_user.id:
                await update.message.reply_text(
                    "Kontakt sizga tegishli emas. Iltimos, o'z kontaktingizni yuboring.",
                    reply_markup=ReplyKeyboardMarkup(
                        [[KeyboardButton(text="📱 Telefonni yuborish", request_contact=True)]],
                        resize_keyboard=True,
                        one_time_keyboard=True,
                    ),
                )
                return
            clean_phone = contact.phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            phone_verified = True
            if not _re.fullmatch(r"\+?\d{7,15}", clean_phone):
                await update.message.reply_text(
                    "Noto'g'ri telefon raqam. Iltimos, tugmani qayta bosing.",
                    reply_markup=ReplyKeyboardMarkup(
                        [[KeyboardButton(text="📱 Telefonni yuborish", request_contact=True)]],
                        resize_keyboard=True,
                        one_time_keyboard=True,
                    ),
                )
                return
        else:
            # Only verified contact allowed — reject typed numbers
            keyboard = ReplyKeyboardMarkup(
                [[KeyboardButton(text="📱 Telefonni yuborish", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await update.message.reply_text(
                "Iltimos, telefon raqamingizni tasdiqlash uchun tugmani bosing:\n📱 Telefonni yuborish",
                reply_markup=keyboard,
            )
            return

        full_name = context.user_data.get("auth_name", "")

        # An unverified legacy link must not produce a login code. The code
        # redemption path would otherwise authenticate an unresolved account.
        user = await _get_or_create_user_async(update)
        if user is None:
            context.user_data.pop("auth_state", None)
            context.user_data.pop("auth_token", None)
            context.user_data.pop("auth_name", None)
            await update.message.reply_text(
                "Telegram hisobingiz bog'lanishini qayta tasdiqlang yoki administratorga murojaat qiling.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        # One true number: verified phone must be unique across accounts
        def _phone_taken():
            from apps.accounts.models import Profile
            return Profile.objects.filter(phone=clean_phone).exclude(user=user).exists()

        if phone_verified and await _run_db(_phone_taken):
            await update.message.reply_text(
                "Bu telefon raqami boshqa hisobga bog'langan. Boshqa raqam bilan urinib ko'ring yoki administratorga murojaat qiling.",
                reply_markup=ReplyKeyboardRemove(),
            )
            context.user_data.pop("auth_state", None)
            context.user_data.pop("auth_token", None)
            context.user_data.pop("auth_name", None)
            return

        # Save to DB and generate short code (atomic guard against reuse)
        def _save_and_generate():
            try:
                at = TelegramAuthToken.objects.get(token=auth_token_str)
            except TelegramAuthToken.DoesNotExist:
                return None
            if at.is_expired or at.consumed_at or at.is_verified:
                return None
            at.full_name = full_name
            at.phone_number = clean_phone
            at.phone_verified = phone_verified
            at.conversation_state = "code_displayed"
            # Generate 6-digit code
            code = at.generate_short_code()
            at.save(update_fields=["full_name", "phone_number", "phone_verified", "conversation_state", "short_code"])
            return code

        code = await _run_db(_save_and_generate)

        if code is None:
            await update.message.reply_text(
                "❌ Token eskirgan yoki topilmadi.\n"
                "Veb-saytda qaytadan 'Telegram orqali kirish' tugmasini bosing."
            )
            context.user_data.pop("auth_state", None)
            context.user_data.pop("auth_token", None)
            context.user_data.pop("auth_name", None)
            return

        # Mark token as verified
        def _verify_token():
            try:
                at = TelegramAuthToken.objects.get(token=auth_token_str)
            except TelegramAuthToken.DoesNotExist:
                return False
            if user:
                at.user = user
                at.telegram_chat_id = tg_user.id if tg_user else None
                at.is_verified = True
                at.verified_at = timezone.now()
                at.save(update_fields=["user", "telegram_chat_id", "is_verified", "verified_at"])
            return True

        await _run_db(_verify_token)

        # Update user profile with collected info + verified phone sync
        if user and full_name:
            name_parts = full_name.split(" ", 1)
            user.first_name = name_parts[0]
            user.last_name = name_parts[1] if len(name_parts) > 1 else ""
            await _run_db(user.save, update_fields=["first_name", "last_name"])
            if phone_verified and clean_phone:
                def _sync_phone():
                    from apps.accounts.models import Profile
                    profile, _ = Profile.objects.get_or_create(user=user)
                    # Only overwrite if empty or same verified number
                    if not profile.phone or profile.phone == clean_phone:
                        profile.phone = clean_phone
                        profile.save(update_fields=["phone"])
                await _run_db(_sync_phone)

        # Show the 6-digit code with visual display (remove contact keyboard)
        code_display = "  ".join(code)
        verified_badge = "✅ tasdiqlangan" if phone_verified else "⚠️ qo'lda kiritilgan"
        await update.message.reply_text(
            f"🎉 *Ma'lumotlar saqlandi!*\n\n"
            f"👤 Ism: *{full_name}*\n"
            f"📱 Telefon: `{clean_phone}` ({verified_badge})\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔑 *SIZNING KODINGIZ:*\n\n"
            f"`{code_display}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⏰ Kod 10 daqiqa ichida eskiradi.\n\n"
            f"🌐 Veb-saytda shu kodni kiriting:\n"
            f"1. \"Telegram orqali kirish\" tugmasini bosing\n"
            f"2. Kodni kiriting\n"
            f"3. Tizimga kiring!\n\n"
            f"_Birinchi marta kiryapsizmi? Bot avtomatik hisob yaratadi._",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )

        # Clear conversation state
        context.user_data.pop("auth_state", None)
        context.user_data.pop("auth_token", None)
        context.user_data.pop("auth_name", None)

        logger.info(
            "TG auth code generated: user=%s, tg_id=%s, phone_verified=%s",
            full_name, tg_user.id if tg_user else "?", phone_verified,
        )


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    text = (
        "📋 *Bot buyruqlari:*\n\n"
        "/start — Botni qayta ishga tushirish\n"
        "/help — Yordam\n"
        "/quiz — 🧠 *Telegram Quiz* — test topshirish\n"
        "/arena — ⚔️ *1v1 Arena* — ELO reyting, duellar\n"
        "/arena_join KOD — 🔗 invite kod bilan xonaga qo'shilish\n"
        "/results — *Barcha natijalar* (test + esse + tahlil)\n"
        "/profile — Shaxsiy profilingiz\n"
        "/tests — Mavjud testlar\n"
        "/essays — Esse mavzulari\n"
        "/leaderboard — *Reyting* (eng yaxshilar)\n"
        "/streak — *Kunlik streak* (kirishlar)\n"
        "/daily — *Kunlik vazifalar*\n\n"
        "🌐 *Web platforma:*\n"
        "Barcha funksiyalar to'liq ishlashi uchun "
        "veb-saytda tizimga kiring."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /profile
# ---------------------------------------------------------------------------

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile command — show user stats."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    from apps.results.models import Result, Certificate
    from apps.essays.models import EssaySubmission
    from apps.games.models import UserGameScore, UserBadge

    def _get_profile_data():
        results = Result.objects.filter(student=user)
        essays = EssaySubmission.objects.filter(student=user)
        game_scores = list(UserGameScore.objects.filter(user=user))
        certificates = Certificate.objects.filter(student=user)
        badges = UserBadge.objects.filter(user=user)
        total_xp = sum(gs.total_xp for gs in game_scores)
        total_coins = sum(gs.total_coins for gs in game_scores)
        return {
            "test_count": results.count(),
            "passed_count": results.filter(is_passed=True).count(),
            "essay_count": essays.count(),
            "graded_count": essays.filter(status='graded').count(),
            "cert_count": certificates.count(),
            "games_played": sum(gs.games_played for gs in game_scores),
            "total_xp": total_xp,
            "total_coins": total_coins,
            "badge_count": badges.count(),
        }

    data = await _run_db(_get_profile_data)

    text = (
        f"👤 *Profil*\n\n"
        f"📛 Ism: *{user.get_full_name()}*\n"
        f"📧 Email: `{user.email}`\n"
        f"🎭 Roli: *{user.get_role_display() if hasattr(user, 'get_role_display') else user.role}*\n\n"
        f"📊 *Statistika:*\n"
        f"  📝 Testlar: *{data['test_count']}* topshirish, *{data['passed_count']}* o'tilgan\n"
        f"  ✍️ Esselar: *{data['essay_count']}* yozilgan, *{data['graded_count']}* baholangan\n"
        f"  🏆 Sertifikatlar: *{data['cert_count']}*\n"
        f"  🎮 O'yinlar: *{data['games_played']}* o'ynalgan\n"
        f"  ⚡ XP: *{data['total_xp']}*\n"
        f"  🪙 Tanga: *{data['total_coins']}*\n"
        f"  🎖️ Badgelar: *{data['badge_count']}*"
    )

    await send_reply(update, text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /tests
# ---------------------------------------------------------------------------

async def tests_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tests command — show available tests."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    from apps.tests.models import Test
    from django.conf import settings as _settings
    site_url = getattr(_settings, "SITE_URL", "http://localhost:8000")

    tests = await _run_db(lambda: list(Test.objects.filter(is_active=True).select_related("course").order_by("-created_at")[:10]))

    if not tests:
        await send_reply(
            update,
            "📝 Hozircha mavjud testlar yo'q.\n\n"
            "O'qituvchilar yangi testlar yaratganda, ular shu yerda paydo bo'ladi.",
            reply_markup=_main_menu_keyboard(),
        )
        return

    text = "📝 *Mavjud testlar:*\n\n"
    buttons = []

    for i, test in enumerate(tests, 1):
        diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(test.difficulty, "⚪")
        text += (
            f"{i}. {diff_emoji} *{test.title}*\n"
            f"   📚 {test.course.title}\n"
            f"   ⏱ {test.time_limit_minutes} daqiqa · {test.total_questions} savol\n\n"
        )
        buttons.append([
            InlineKeyboardButton(
                f"▶️ {test.title[:30]}",
                url=f"{site_url}/tests/{test.id}/take/",
            )
        ])

    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")])

    await send_reply(
        update,
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )



# ---------------------------------------------------------------------------
# /results — Barcha natijalar (test + esse + tahlil)
# ---------------------------------------------------------------------------

async def _show_students_results(update: Update, context: ContextTypes.DEFAULT_TYPE, teacher) -> None:
    """Show all students' results for teachers/admins."""

    def _get_students_overview():
        from django.contrib.auth import get_user_model
        from django.db.models import Avg, Count, Q, Value
        from django.db.models.functions import Coalesce
        from apps.results.models import Result
        from apps.essays.models import EssaySubmission

        User = get_user_model()

        # Aggregated test stats per student — 1 query instead of N+1
        test_rows = (
            Result.objects.filter(student__role="student")
            .values("student_id")
            .annotate(
                test_count=Count("id"),
                test_avg=Coalesce(Avg("percentage"), Value(0)),
                test_passed=Count("id", filter=Q(is_passed=True)),
            )
        )
        test_stats = {
            r["student_id"]: r for r in test_rows
        }

        # Aggregated graded-essay stats per student
        essay_rows = (
            EssaySubmission.objects.filter(student__role="student", status="graded")
            .values("student_id")
            .annotate(
                essay_count=Count("id"),
                essay_avg=Coalesce(Avg("total_score"), Value(0)),
            )
        )
        essay_stats = {
            r["student_id"]: r for r in essay_rows
        }

        overview = []
        for student in User.objects.filter(role="student").order_by("first_name"):
            t = test_stats.get(student.id, {})
            e = essay_stats.get(student.id, {})
            test_count = t.get("test_count", 0)
            essay_count = e.get("essay_count", 0)

            if test_count > 0 or essay_count > 0:
                overview.append({
                    "id": student.id,
                    "name": student.get_full_name() or student.email,
                    "test_count": test_count,
                    "test_avg": round(float(t.get("test_avg") or 0), 1),
                    "test_passed": t.get("test_passed", 0),
                    "essay_count": essay_count,
                    "essay_avg": round(float(e.get("essay_avg") or 0), 1),
                })

        # Sort by overall score (descending)
        overview.sort(key=lambda x: (x["test_avg"] + x["essay_avg"] * 100 / 24) / 2, reverse=True)
        return overview

    students = await _run_db(_get_students_overview)

    if not students:
        await send_reply(
            update,
            "📊 *O'quvchilar natijalari*\n\n"
            "Hali hech qanday o'quvchi natija ko'rsatmagan.",
            parse_mode="Markdown",
            reply_markup=_main_menu_keyboard(),
        )
        return

    lines = ["📊 *O'QUVCHILAR NATIJALARI*\n"]

    # Top 3 badge
    medals = ["🥇", "🥈", "🥉"]
    for i, s in enumerate(students[:20]):  # Top 20
        medal = medals[i] if i < 3 else f"{i+1}."
        grade = "A" if s["test_avg"] >= 80 else "B" if s["test_avg"] >= 60 else "C" if s["test_avg"] >= 40 else "D"
        lines.append(
            f"{medal} *{s['name']}*\n"
            f"   📝 {s['test_count']} test (o'rt: {s['test_avg']}%) {grade}\n"
            f"   ✍️ {s['essay_count']} esse (o'rt: {s['essay_avg']}/24)"
        )

    if len(students) > 20:
        lines.append(f"\n... va yana *{len(students) - 20}* o'quvchi")

    # Buttons for each student (first 8)
    buttons = []
    for s in students[:8]:
        buttons.append([
            InlineKeyboardButton(
                f"👤 {s['name'][:25]}",
                callback_data=f"student_result_{s['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")])

    await send_reply(
        update,
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def _show_student_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, student_id: int) -> None:
    """Show detailed results for a specific student (teacher/admin view)."""

    def _get_student_detail():
        from django.contrib.auth import get_user_model
        from django.conf import settings
        from django.db.models import Avg
        from apps.results.models import Result
        from apps.essays.models import EssaySubmission

        User = get_user_model()
        student = User.objects.filter(id=student_id, role="student").first()
        if not student:
            return None

        test_results = list(
            Result.objects.filter(student=student)
            .select_related("test")
            .order_by("-calculated_at")[:10]
        )
        essay_results = list(
            EssaySubmission.objects.filter(student=student, status="graded")
            .select_related("topic")
            .order_by("-graded_at")[:10]
        )

        all_tests = Result.objects.filter(student=student)
        all_essays = EssaySubmission.objects.filter(student=student, status="graded")

        test_avg = 0
        test_passed = 0
        test_total = all_tests.count()
        if test_total > 0:
            test_avg = round(float(all_tests.aggregate(avg=Avg("percentage"))["avg"] or 0), 1)
            test_passed = all_tests.filter(is_passed=True).count()

        essay_avg = 0
        essay_count = all_essays.count()
        if essay_count > 0:
            essay_avg = round(float(all_essays.aggregate(avg=Avg("total_score"))["avg"] or 0), 1)

        target = getattr(settings, "ESSAY_TARGET_SCALE", 75)

        return {
            "student": student,
            "test_results": test_results,
            "essay_results": essay_results,
            "test_total": test_total,
            "test_passed": test_passed,
            "test_avg": test_avg,
            "essay_count": essay_count,
            "essay_avg": essay_avg,
            "essay_target": target,
        }

    data = await _run_db(_get_student_detail)

    if not data:
        await send_reply(update, "O'quvchi topilmadi.")
        return

    s = data["student"]
    lines = [
        f"👤 *{s.get_full_name()}* natijalari\n",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    # Test results
    if data["test_results"]:
        lines.append("📝 *TEST NATIJALARI*\n")
        for r in data["test_results"]:
            icon = "✅" if r.is_passed else "❌"
            lines.append(
                f"{icon} *{r.test.title}* — {r.percentage}%"
            )
        lines.append(f"\n📊 O'rtacha: *{data['test_avg']}%* ({data['test_passed']}/{data['test_total']} o'tilgan)")
    else:
        lines.append("📝 Testlar: yo'q")

    # Essay results
    if data["essay_results"]:
        lines.append("\n✍️ *ESSE NATIJALARI*\n")
        for e in data["essay_results"]:
            topic = e.topic.title if e.topic else "?"
            score = float(e.total_score) if e.total_score else 0
            lines.append(
                f"• *{topic}* — {score}/24"
            )
        lines.append(f"\n📊 O'rtacha: *{data['essay_avg']}/24*")
    else:
        lines.append("\n✍️ Esselar: yo'q")

    # Back button
    buttons = [[InlineKeyboardButton("🔙 Orqaga", callback_data="menu_results")]]

    await send_reply(
        update,
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

async def results_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /results command — show ALL results with analysis.

    For students: own results.
    For teachers/admins: all students' results + individual student view.
    """
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    # --- Teacher/Admin: show all students ---
    if user.role in ("teacher", "admin"):
        await _show_students_results(update, context, user)
        return

    from django.conf import settings

    def _get_all_results():
        from apps.results.models import Result
        from apps.essays.models import EssaySubmission

        # Test results
        test_results = list(
            Result.objects.filter(student=user)
            .select_related("test")
            .order_by("-calculated_at")[:10]
        )

        # Essay results
        essay_results = list(
            EssaySubmission.objects.filter(student=user, status="graded")
            .select_related("topic")
            .order_by("-graded_at")[:10]
        )

        # Stats
        all_tests = Result.objects.filter(student=user)
        all_essays = EssaySubmission.objects.filter(student=user, status="graded")

        test_avg = 0
        test_passed = 0
        test_total = all_tests.count()
        if test_total > 0:
            from django.db.models import Avg
            avg_data = all_tests.aggregate(avg=Avg("percentage"))
            test_avg = round(float(avg_data["avg"] or 0), 1)
            test_passed = all_tests.filter(is_passed=True).count()

        essay_avg = 0
        essay_count = all_essays.count()
        if essay_count > 0:
            from django.db.models import Avg
            avg_data = all_essays.aggregate(avg=Avg("total_score"))
            essay_avg = round(float(avg_data["avg"] or 0), 1)

        target = getattr(settings, "ESSAY_TARGET_SCALE", 75)

        return {
            "test_results": test_results,
            "essay_results": essay_results,
            "test_total": test_total,
            "test_passed": test_passed,
            "test_avg": test_avg,
            "essay_count": essay_count,
            "essay_avg": essay_avg,
            "essay_target": target,
        }

    data = await _run_db(_get_all_results)

    has_tests = len(data["test_results"]) > 0
    has_essays = len(data["essay_results"]) > 0

    if not has_tests and not has_essays:
        await send_reply(
            update,
            "📊 *Barcha natijalar*\n\n"
            "Hali natijalar yo'q.\n\n"
            "📝 Test topshiring yoki ✍️ esse yozing!",
            parse_mode="Markdown",
            reply_markup=_main_menu_keyboard(),
        )
        return

    # --- Build message ---
    lines = ["📊 *BARCHA NATIJALAR*\n"]

    # --- Test results section ---
    if has_tests:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📝 *TEST NATIJALARI*\n")

        for i, r in enumerate(data["test_results"], 1):
            icon = "✅" if r.is_passed else "❌"
            lines.append(
                f"{icon} *{r.test.title}*\n"
                f"   📈 {r.percentage}%  ({r.correct_answers}/{r.total_questions})\n"
                f"   📅 {r.calculated_at.strftime('%d.%m.%Y')}"
            )

        lines.append("")
        lines.append(
            f"📊 *Test xulosasi:*\n"
            f"   Jami: *{data['test_total']}* topshirish\n"
            f"   O'tilgan: *{data['test_passed']}* ✅\n"
            f"   O'tmagan: *{data['test_total'] - data['test_passed']}* ❌\n"
            f"   O'rtacha ball: *{data['test_avg']}%*"
        )

    # --- Essay results section ---
    if has_essays:
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("✍️ *ESSE NATIJALARI*\n")

        for i, e in enumerate(data["essay_results"], 1):
            topic_name = e.topic.title if e.topic else "Mavzu yo'q"
            score = float(e.total_score) if e.total_score else 0
            converted = round(score / 24 * data["essay_target"]) if score > 0 else 0
            grade = "A" if score >= 20 else "B" if score >= 16 else "C" if score >= 12 else "D" if score >= 8 else "F"

            lines.append(
                f"{i}. *{topic_name}*\n"
                f"   🎯 {score}/24 ball ({grade})\n"
                f"   📐 ~{converted}/{data['essay_target']} umumiy tizimda\n"
                f"   📅 {e.graded_at.strftime('%d.%m.%Y') if e.graded_at else 'N/A'}"
            )

        lines.append("")
        lines.append(
            f"📊 *Esse xulosasi:*\n"
            f"   Jami: *{data['essay_count']}* esse baholangan\n"
            f"   O'rtacha ball: *{data['essay_avg']}/24*\n"
            f"   O'rtacha (umumiy): *{round(data['essay_avg'] / 24 * data['essay_target'])}/{data['essay_target']}*"
        )

    # --- Overall analysis ---
    if has_tests and has_essays:
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📋 *UMUMIY TAHHLIL*\n")

        # Strength/weakness
        if data["test_avg"] >= 70 and data["essay_avg"] >= 16:
            lines.append("💪 *Kuchli tomonlaringiz:*")
            lines.append("   Testlarda va esselarda yaxshi natijalar ko'rsatmoqdasiz!")
        elif data["test_avg"] >= 70:
            lines.append("💪 *Testlar:* Yaxshi natija!")
            lines.append("⚠️ *Esselar:* Ko'proq mashq qiling.")
        elif data["essay_avg"] >= 16:
            lines.append("💪 *Esselar:* Yaxshi yozayapsiz!")
            lines.append("⚠️ *Testlar:* Ko'proq tayyorlaning.")
        else:
            lines.append("⚠️ *Tavsiya:*")
            lines.append("   Har kuni 1 ta test topshiring va 1 ta esse yozing.")

        # Conversion
        test_converted = round(data["test_avg"] / 100 * data["essay_target"])
        essay_converted = round(data["essay_avg"] / 24 * data["essay_target"])
        overall = round((test_converted + essay_converted) / 2)

        lines.append("")
        lines.append(
            f"📈 *Umumiy baho:* ~*{overall}/{data['essay_target']}*\n"
            f"   (Testlar: ~{test_converted} + Esselar: ~{essay_converted})"
        )

    text = "\n".join(lines)

    # Telegram max message length is 4096
    if len(text) > 4000:
        text = text[:3950] + "\n\n... (to'liq versiya veb-saytda)"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Testlar", callback_data="menu_tests"),
            InlineKeyboardButton("✍️ Esselar", callback_data="menu_essays"),
        ],
        [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
    ])

    await send_reply(update, text, parse_mode="Markdown", reply_markup=keyboard)


# ---------------------------------------------------------------------------
# /essays
# ---------------------------------------------------------------------------

async def essays_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /essays command — show essay topics."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    from apps.essays.models import EssayTopic, EssaySubmission

    def _get_essay_data():
        topics = list(EssayTopic.objects.filter(is_active=True).order_by("-created_at")[:10])
        user_subs = {
            s.topic_id: s
            for s in EssaySubmission.objects.filter(student=user)
        }
        return topics, user_subs

    topics, user_subs = await _run_db(_get_essay_data)

    from django.conf import settings as _settings
    site_url = getattr(_settings, "SITE_URL", "http://localhost:8000")

    if not topics:
        await send_reply(
            update,
            "✍️ Hali esse mavzulari yo'q.\n\n"
            "O'qituvchilar yangi mavzular yaratganda, ular shu yerda paydo bo'ladi.",
            reply_markup=_main_menu_keyboard(),
        )
        return

    text = "✍️ *Esse mavzulari:*\n\n"
    buttons = []

    for i, topic in enumerate(topics, 1):
        lock = "🔒" if topic.password else "📝"
        sub = user_subs.get(topic.id)
        if sub:
            if sub.status == "graded":
                status = f"✅ {sub.total_score}/{sub.max_score}" if sub.total_score else "✅ Baholangan"
            else:
                status = f"⏳ {sub.get_status_display()}"
        else:
            status = "🆕 Yangi"

        text += (
            f"{i}. {lock} *{topic.title}*\n"
            f"   📏 {topic.word_limit_min}-{topic.word_limit_max} so'z · ⏱ {topic.time_limit_minutes} daqiqa\n"
            f"   📌 Holat: {status}\n\n"
        )

        if not sub or sub.status == "draft":
            buttons.append([
                InlineKeyboardButton(
                    f"✍️ {topic.title[:30]}",
                    url=f"{site_url}/essays/{topic.id}/start/",
                )
            ])

    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")])

    await send_reply(
        update,
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------------------------------------------------------------------------
# Inline keyboard callback handlers
# ---------------------------------------------------------------------------

async def _dispatch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, handler) -> None:
    """Dispatch to a handler that uses send_reply — safe from both message and callback.

    The handler must use send_reply() instead of update.message.reply_text().
    """
    await handler(update, context)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard callback queries."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "menu_main":
        await query.edit_message_text(
            "🎓 *Ona Tili & Adabiyot* — Bosh menyu\n\n"
            "Quyidagi tugmalardan foydalaning 👇",
            parse_mode="Markdown",
            reply_markup=_main_menu_keyboard(),
        )
    elif data == "menu_tests":
        # Simulate /tests command
        user = await _get_or_create_user_async(update)
        if user:
            from apps.tests.models import Test
            from django.conf import settings as _settings
            site_url = getattr(_settings, "SITE_URL", "http://localhost:8000")
            tests = await _run_db(lambda: list(Test.objects.filter(is_active=True).select_related("course").order_by("-created_at")[:8]))

            if not tests:
                await query.edit_message_text("📝 Hozircha mavjud testlar yo'q.")
                return

            text = "📝 *Mavjud testlar:*\n\n"
            buttons = []
            for test in tests:
                diff = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(test.difficulty, "⚪")
                text += f"{diff} *{test.title}* — {test.total_questions} savol\n"
                buttons.append([
                    InlineKeyboardButton(
                        f"▶️ {test.title[:30]}",
                        url=f"{site_url}/tests/{test.id}/take/",
                    )
                ])

            buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "menu_results":
        await _dispatch_handler(update, context, results_handler)
    elif data == "menu_profile":
        await _dispatch_handler(update, context, profile_handler)
    elif data == "menu_essays":
        await _dispatch_handler(update, context, essays_handler)
    elif data == "menu_leaderboard":
        await _dispatch_handler(update, context, leaderboard_handler)
    elif data == "menu_streak":
        await _dispatch_handler(update, context, streak_handler)
    elif data == "menu_daily":
        await _dispatch_handler(update, context, daily_handler)
    elif data == "menu_arena":
        await _dispatch_handler(update, context, arena_handler)
    elif data == "menu_premium":
        await _dispatch_handler(update, context, premium_handler)
    elif data.startswith("buy_plan_"):
        plan_id = _safe_callback_int(data, prefix="buy_plan_")
        if plan_id is not None:
            await buy_plan_callback(update, context, plan_id)
    elif data.startswith("approve_payment_"):
        payment_id = _safe_callback_int(data, prefix="approve_payment_")
        if payment_id is not None:
            await approve_payment_callback(update, context, payment_id)
    elif data.startswith("reject_payment_"):
        payment_id = _safe_callback_int(data, prefix="reject_payment_")
        if payment_id is not None:
            await reject_payment_callback(update, context, payment_id)
    elif data.startswith("student_result_"):
        student_id = _safe_callback_int(data, prefix="student_result_")
        if student_id is not None:
            await _dispatch_handler(update, context, lambda u, c: _show_student_detail(u, c, student_id))
    else:
        # Unknown callback data — acknowledge so the client stops spinning
        await query.edit_message_text("😕 Bu tugma endi ishlamaydi. /start ni bosing.")


# ---------------------------------------------------------------------------
# /leaderboard — ranking
# ---------------------------------------------------------------------------

async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /leaderboard command — top students by XP + test scores."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    def _get_leaderboard():
        from django.db.models import Avg, Sum, Count, Value
        from django.db.models.functions import Coalesce
        from apps.games.models import UserGameScore
        from apps.results.models import Result
        from apps.accounts.models import User

        # Aggregate all stats up-front (constant number of queries instead of
        # a per-student loop that previously issued 3+ queries per student).
        xp_rows = (
            UserGameScore.objects.filter(user__role="student")
            .values("user_id")
            .annotate(
                total_xp=Coalesce(Sum("total_xp"), Value(0)),
                total_coins=Coalesce(Sum("total_coins"), Value(0)),
            )
        )
        xp_stats = {r["user_id"]: r for r in xp_rows}

        result_rows = (
            Result.objects.filter(student__role="student")
            .values("student_id")
            .annotate(
                test_count=Count("id"),
                test_avg=Coalesce(Avg("percentage"), Value(0)),
            )
        )
        result_stats = {r["student_id"]: r for r in result_rows}

        leaderboard = []
        for student in User.objects.filter(role="student"):
            x = xp_stats.get(student.id, {})
            r = result_stats.get(student.id, {})
            total_xp = x.get("total_xp") or 0
            test_count = r.get("test_count", 0)
            test_avg = r.get("test_avg") or 0

            if total_xp > 0 or test_count > 0:
                leaderboard.append({
                    "name": student.get_full_name() or student.email,
                    "total_xp": total_xp,
                    "total_coins": x.get("total_coins") or 0,
                    "test_count": test_count,
                    "test_avg": round(float(test_avg), 1),
                })

        leaderboard.sort(key=lambda x: x["total_xp"], reverse=True)
        return leaderboard[:15]

    leaderboard = await _run_db(_get_leaderboard)

    if not leaderboard:
        await send_reply(
            update,
            "🏆 *Leaderboard*\n\n"
            "Hali reyting yo'q. Test topshiring yoki o'yin o'ynang!",
            parse_mode="Markdown",
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 *LEADERBOARD*\n"]

    for i, s in enumerate(leaderboard):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(
            f"{medal} *{s['name']}*\n"
            f"   ⚡ {s['total_xp']} XP · 🪙 {s['total_coins']} tanga\n"
            f"   📝 {s['test_count']} test (o'rt: {s['test_avg']}%)"
        )

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3950] + "\n\n..."

    await send_reply(update, text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /streak — kunlik streak
# ---------------------------------------------------------------------------

async def streak_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /streak command — show daily streak info."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    def _get_streak_data():
        from apps.games.models import DailyStreak
        from django.utils import timezone

        streak_obj, _ = DailyStreak.objects.get_or_create(user=user)
        result = streak_obj.update_streak()

        # Reward info
        rewards = []
        milestones = [
            (3, 30, streak_obj.reward_3claimed),
            (7, 75, streak_obj.reward_7claimed),
            (14, 150, streak_obj.reward_14claimed),
            (30, 500, streak_obj.reward_30claimed),
        ]
        for days, xp, claimed in milestones:
            status = "✅" if claimed else "⬜"
            rewards.append(f"  {status} {days} kun — +{xp} XP")

        return {
            "current_streak": streak_obj.current_streak,
            "best_streak": streak_obj.best_streak,
            "total_logins": streak_obj.total_logins,
            "rewards": rewards,
            "reward_claimed": result.get("reward_claimed"),
            "xp_earned": result.get("xp_earned", 0),
        }

    data = await _run_db(_get_streak_data)

    streak = data["current_streak"]
    fire = "🔥" * min(streak, 10) if streak > 0 else "❄️"

    lines = [
        f"🔥 *KUNLIK STREAK*\n",
        f"{fire}\n",
        f"📅 Joriy streak: *{streak} kun*",
        f"🏆 Eng uzun: *{data['best_streak']} kun*",
        f"📊 Jami kirishlar: *{data['total_logins']}*",
        "",
        "🎁 *Streak mukofotlari:*",
    ]
    lines.extend(data["rewards"])

    if data["reward_claimed"]:
        lines.append(f"\n🎉 *Tabriklaymiz!* +{data['xp_earned']} XP olindi!")

    text = "\n".join(lines)
    await send_reply(update, text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /daily — kunlik vazifa
# ---------------------------------------------------------------------------

async def daily_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /daily command — daily tasks & rewards."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    def _get_daily_data():
        from django.utils import timezone
        from apps.results.models import Result
        from apps.essays.models import EssaySubmission
        from apps.games.models import UserGameScore, DailyStreak
        from datetime import timedelta

        today = timezone.now().date()
        today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))

        # Today's activity
        tests_today = Result.objects.filter(student=user, calculated_at__gte=today_start).count()
        essays_today = EssaySubmission.objects.filter(student=user, submitted_at__gte=today_start).count()
        games_today = UserGameScore.objects.filter(user=user, last_played_at__gte=today_start).count()

        # Tasks
        tasks = []
        tasks.append({"name": "1 ta test topshirish", "done": tests_today >= 1, "reward": "+10 XP"})
        tasks.append({"name": "1 ta esse yozish", "done": essays_today >= 1, "reward": "+15 XP"})
        tasks.append({"name": "1 ta o'yin o'ynash", "done": games_today >= 1, "reward": "+5 XP"})
        tasks.append({"name": "3 ta test topshirish", "done": tests_today >= 3, "reward": "+25 XP"})

        completed = sum(1 for t in tasks if t["done"])
        total_xp = sum(gs.total_xp for gs in UserGameScore.objects.filter(user=user))

        return {
            "tasks": tasks,
            "completed": completed,
            "total_tasks": len(tasks),
            "total_xp": total_xp,
        }

    data = await _run_db(_get_daily_data)

    lines = ["📋 *KUNLIK VAZIFALAR*\n"]

    for task in data["tasks"]:
        icon = "✅" if task["done"] else "⬜"
        lines.append(f"{icon} {task['name']}  ({task['reward']})")

    lines.append(f"\n📊 Tugallangan: *{data['completed']}/{data['total_tasks']}*")
    lines.append(f"⚡ Jami XP: *{data['total_xp']}*")

    if data["completed"] == data["total_tasks"]:
        lines.append("\n🎉 *Barcha vazifalar bajarildi! Ajoyib!*")

    text = "\n".join(lines)
    await send_reply(update, text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /premium — obuna olish
# ---------------------------------------------------------------------------

async def premium_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /premium command — show subscription plans, card number, and payment flow."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    def _get_sub_info():
        from apps.payments.models import UserSubscription, SubscriptionPlan

        user_sub = getattr(user, "subscription", None)
        plans = list(SubscriptionPlan.objects.filter(is_active=True, plan_type__in=["premium", "family"]).order_by("sort_order"))

        return {
            "has_sub": user_sub is not None and user_sub.is_active,
            "plan_name": user_sub.plan.name if user_sub and user_sub.is_active else None,
            "expires_at": user_sub.expires_at if user_sub else None,
            "days_remaining": user_sub.days_remaining if user_sub else 0,
            "plans": plans,
        }

    data = await _run_db(_get_sub_info)

    if data["has_sub"]:
        text = (
            f"💎 *Sizning obunangiz*\n\n"
            f"📦 Reja: *{data['plan_name']}*\n"
            f"⏰ Qolgan: *{data['days_remaining']} kun*\n\n"
            f"Barcha premium imkoniyatlar ochiq!"
        )
        await send_reply(update, text, parse_mode="Markdown")
    else:
        # Narxlarni ko'rsatish
        lines = [
            "💎 *PREMIUM OBUNA*\n",
            "Sizga quyidagi imkoniyatlar ochiladi:\n",
            "✅ Cheksiz testlar (kuniga 5 ta emas)",
            "✅ Cheksiz esselar (haftasiga 2 ta emas)",
            "✅ Batafsil tahlil va statistika",
            "✅ PDF sertifikatlar",
            "✅ Ustuvor qo'llab-quvvatlash",
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "💰 *NARXLAR:*\n",
        ]

        buttons_rows = []
        for plan in data["plans"]:
            price = int(plan.price_monthly) if plan.price_monthly else 0
            yearly = int(plan.price_yearly) if plan.price_yearly else 0
            lines.append(f"📦 *{plan.name}* — {price:,} so'm/oy")
            if yearly > 0:
                lines.append(f"   💡 Yillik: {yearly:,} so'm (tejamkor!)")
            lines.append("")
            buttons_rows.append([
                InlineKeyboardButton(
                    f"💳 {plan.name} — {price:,} so'm",
                    callback_data=f"buy_plan_{plan.id}"
                )
            ])

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━",
            "💳 *TO'LOV USULI:*",
            "Karta raqamiga pul o'tkazing,",
            "keyin screenshot'ni menga yuboring.",
            "",
            "Admin tekshirgandan keyin",
            "obunangiz faollashtiriladi.",
        ])

        buttons_rows.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")])

        text = "\n".join(lines)
        await send_reply(update, text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons_rows))


# Payment card details — from settings (PAYMENT_CARD_*) with safe fallbacks
from django.conf import settings as _django_settings

PAYMENT_CARD = getattr(_django_settings, "PAYMENT_CARD_NUMBER", "4073 4200 3846 0386")
PAYMENT_CARD_BANK = getattr(_django_settings, "PAYMENT_CARD_BANK", "Uzum Bank")
PAYMENT_CARD_HOLDER = getattr(_django_settings, "PAYMENT_CARD_HOLDER", "Lobar Mansurova")
PAYMENT_ADMIN_USERNAME = getattr(_django_settings, "PAYMENT_ADMIN_USERNAME", "rozievkomiljon")


async def buy_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: int) -> None:
    """Handle buy_plan_<id> callback — show card number for payment."""
    query = update.callback_query
    # NOTE: query.answer() already called by callback_handler

    user = await _get_or_create_user_async(update)
    if not user:
        await query.edit_message_text("Xatolik yuz berdi.")
        return

    def _get_plan():
        from apps.payments.models import SubscriptionPlan
        return SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()

    plan = await _run_db(_get_plan)
    if not plan:
        await query.edit_message_text("Reja topilmadi.")
        return

    price = int(plan.price_monthly)

    # Store selected plan in context for screenshot verification
    context.user_data["selected_plan_id"] = plan_id
    context.user_data["payment_state"] = "awaiting_screenshot"

    text = (
        f"💳 *To'lov — {plan.name}*\n\n"
        f"💰 Narx: *{price:,} so'm/oy*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 *Karta raqami:*\n"
        f"`{PAYMENT_CARD}`\n\n"
        f"🏦 Bank: *{PAYMENT_CARD_BANK}*\n"
        f"👤 Egasi: *{PAYMENT_CARD_HOLDER}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📲 *QADAMLAR:*\n"
        f"1. Shu kartaga *{price:,} so'm* o'tkazing\n"
        f"2. To'lov screenshot'ini menga yuboring\n"
        f"3. Admin tekshiradi va obunani yoqadi\n\n"
        f"⏰ Screenshot yuborish uchun 10 daqiqa vaqt bor."
    )

    await query.edit_message_text(text, parse_mode="Markdown")


async def payment_screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages — check if it's a payment screenshot."""
    # Check if user is in payment flow
    payment_state = context.user_data.get("payment_state")
    if payment_state != "awaiting_screenshot":
        return  # Not expecting a screenshot

    user = await _get_or_create_user_async(update)
    if not user:
        return

    plan_id = context.user_data.get("selected_plan_id")
    if not plan_id:
        return

    # Get the photo (largest size)
    photo = update.message.photo[-1] if update.message.photo else None
    if not photo:
        await update.message.reply_text("Rasm topilmadi. Qaytadan yuboring.")
        return

    # Save payment request
    def _create_request():
        from django.utils import timezone
        from apps.payments.models import SubscriptionPlan, PaymentRequest

        plan = SubscriptionPlan.objects.filter(id=plan_id).first()
        if not plan:
            return None, "Reja topilmadi"

        # Check if there's already a pending request for this plan
        existing = PaymentRequest.objects.filter(
            user=user, plan=plan, status="pending"
        ).first()
        if existing:
            return None, "Sizda allaqachon tekshirilayotgan to'lov so'rovi bor."

        pr = PaymentRequest.objects.create(
            user=user,
            plan=plan,
            amount=plan.price_monthly,
            telegram_message_id=update.message.message_id,
            screenshot_file_id=photo.file_id,
            status="pending",
        )
        return pr, None

    pr, error = await _run_db(_create_request)

    if error:
        await update.message.reply_text(f"❌ {error}")
        context.user_data.pop("payment_state", None)
        context.user_data.pop("selected_plan_id", None)
        return

    # Clear payment state
    context.user_data.pop("payment_state", None)
    context.user_data.pop("selected_plan_id", None)

    # Confirm to user
    await update.message.reply_text(
        f"✅ *Screenshot qabul qilindi!*\n\n"
        f"📦 Reja: *{pr.plan.name}*\n"
        f"💰 Summa: *{int(pr.amount):,} so'm*\n"
        f"📅 Sana: {pr.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"⏳ Admin tekshirmoqda...\n"
        f"Tekshirilgandan keyin sizga xabar beriladi.",
        parse_mode="Markdown",
    )

    # Notify payment administrators
    await _notify_admins_payment(update, context, pr)

    logger.info(
        "Payment request created: user=%s, plan=%s, amount=%s",
        user.email, pr.plan.name, pr.amount,
    )


async def _notify_admins_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_request) -> None:
    """Notify platform administrators about a new payment request."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    from apps.payments.access import can_manage_payments

    def _get_admins():
        User = get_user_model()
        candidates = (
            User.objects.filter(
                Q(role="admin") | Q(is_superuser=True)
                | Q(user_permissions__codename="change_paymentrequest")
            )
            .filter(is_active=True)
            .exclude(telegram_chat_id__isnull=True)
            .exclude(telegram_identity_verified_at__isnull=True)
            .distinct()
        )
        return [user for user in candidates if can_manage_payments(user)]

    admins = await _run_db(_get_admins)

    if not admins:
        return

    user = payment_request.user
    price = int(payment_request.amount)

    text = (
        f"💰 *YANGI TO'LOV SO'ROVI*\n\n"
        f"👤 Foydalanuvchi: *{user.get_full_name()}*\n"
        f"📧 Email: `{user.email}`\n"
        f"📦 Reja: *{payment_request.plan.name}*\n"
        f"💰 Summa: *{price:,} so'm*\n"
        f"📅 Sana: {payment_request.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📸 Screenshot xabarida yuborildi.\n"
        f"Tekshirib, tasdiqlang yoki rad eting."
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_payment_{payment_request.id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_payment_{payment_request.id}"),
        ],
    ])

    for admin in admins:
        try:
            await context.bot.send_message(
                chat_id=admin.telegram_chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=buttons,
            )
        except Exception as e:
            logger.warning("Failed to notify admin %s: %s", admin.email, e)


async def approve_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: int) -> None:
    """Handle approve_payment_<id> — admin approves payment."""
    query = update.callback_query
    # NOTE: query.answer() already called by callback_handler

    admin_user = await _get_or_create_user_async(update)
    from apps.payments.access import can_manage_payments
    if not can_manage_payments(admin_user):
        await query.edit_message_text("Sizda ruxsat yo'q.")
        return

    def _approve():
        from datetime import timedelta

        from django.db import transaction
        from django.utils import timezone

        from apps.payments.models import PaymentHistory, PaymentRequest, UserSubscription

        with transaction.atomic():
            # Row-lock the request so two admins approving the same payment
            # (or a concurrent reject) serialize; the status re-check inside
            # the lock makes the whole approve→subscribe→log flow atomic —
            # a crash mid-way can never leave a paid request un-activated.
            try:
                pr = (
                    PaymentRequest.objects.select_for_update()
                    .get(id=payment_id, status="pending")
                )
            except PaymentRequest.DoesNotExist:
                return False, "To'lov so'rovi topilmadi yoki allaqachon ko'rib chiqilgan."

            pr.status = "approved"
            pr.reviewed_by = admin_user
            pr.reviewed_at = timezone.now()
            pr.save(update_fields=["status", "reviewed_by", "reviewed_at"])

            # Activate subscription
            existing_sub = getattr(pr.user, "subscription", None)
            if existing_sub and existing_sub.is_active:
                # Extend current subscription
                if existing_sub.expires_at:
                    existing_sub.expires_at += timedelta(days=30)
                else:
                    existing_sub.expires_at = timezone.now() + timedelta(days=30)
                existing_sub.plan = pr.plan
                existing_sub.payment_method = "card"
                existing_sub.save()
            else:
                UserSubscription.objects.create(
                    user=pr.user,
                    plan=pr.plan,
                    status="active",
                    started_at=timezone.now(),
                    expires_at=timezone.now() + timedelta(days=30),
                    is_trial=False,
                    payment_method="card",
                )

            # Log payment
            PaymentHistory.objects.create(
                user=pr.user,
                plan=pr.plan,
                amount=pr.amount,
                currency="UZS",
                payment_method="card",
                status="completed",
                description=f"Karta orqali to'lov (admin tasdiqladi: {admin_user.get_full_name()})",
                completed_at=timezone.now(),
            )

        return True, pr

    success, result = await _run_db(_approve)

    if success:
        # Update admin message
        await query.edit_message_text(
            f"✅ *To'lov tasdiqlandi!*\n\n"
            f"👤 Foydalanuvchi: *{result.user.get_full_name()}*\n"
            f"📦 Reja: *{result.plan.name}*\n"
            f"💰 Summa: *{int(result.amount):,} so'm*\n"
            f"👤 Tekshirgan: *{admin_user.get_full_name()}*",
            parse_mode="Markdown",
        )

        if not result.user.telegram_identity_verified_at:
            return
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=result.user.telegram_chat_id,
                text=(
                    f"🎉 *To'lov tasdiqlandi!*\n\n"
                    f"📦 Reja: *{result.plan.name}*\n"
                    f"⏰ Muddat: *30 kun*\n\n"
                    f"Endi barcha premium imkoniyatlar ochiq!\n"
                    f"O'rganishni boshlang! 💪"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning("Failed to notify user %s: %s", result.user.email, e)
    else:
        await query.edit_message_text(f"❌ {result}")


async def reject_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: int) -> None:
    """Handle reject_payment_<id> — admin rejects payment."""
    query = update.callback_query
    # NOTE: query.answer() already called by callback_handler

    admin_user = await _get_or_create_user_async(update)
    from apps.payments.access import can_manage_payments
    if not can_manage_payments(admin_user):
        await query.edit_message_text("Sizda ruxsat yo'q.")
        return

    def _reject():
        from django.db import transaction
        from django.utils import timezone

        from apps.payments.models import PaymentRequest

        with transaction.atomic():
            # Same row-lock as approve: serializes against a concurrent
            # approve so the final status is the last writer, never both.
            try:
                pr = (
                    PaymentRequest.objects.select_for_update()
                    .get(id=payment_id, status="pending")
                )
            except PaymentRequest.DoesNotExist:
                return False, "To'lov so'rovi topilmadi."

            pr.status = "rejected"
            pr.reviewed_by = admin_user
            pr.reviewed_at = timezone.now()
            pr.admin_note = "Admin tomonidan rad etildi"
            pr.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_note"])

        return True, pr

    success, result = await _run_db(_reject)

    if success:
        await query.edit_message_text(
            f"❌ *To'lov rad etildi*\n\n"
            f"👤 Foydalanuvchi: *{result.user.get_full_name()}*\n"
            f"📦 Reja: *{result.plan.name}*\n"
            f"👤 Tekshirgan: *{admin_user.get_full_name()}*",
            parse_mode="Markdown",
        )

        if not result.user.telegram_identity_verified_at:
            return
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=result.user.telegram_chat_id,
                text=(
                    f"❌ *To'lov rad etildi*\n\n"
                    f"📦 Reja: *{result.plan.name}*\n"
                    f"Summa: {int(result.amount):,} so'm\n\n"
                    f"Sabab: To'lov tasdiqlanmadi.\n"
                    f"Qaytadan urinib ko'ring yoki admin bilan bog'laning."
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning("Failed to notify user %s: %s", result.user.email, e)
    else:
        await query.edit_message_text(f"❌ {result}")


# ---------------------------------------------------------------------------
# /arena — 1v1 Quiz Arena
# ---------------------------------------------------------------------------

def _arena_leaderboard_text(top: int = 5) -> str:
    """Top players by ELO rating (excluding bots)."""
    from apps.arena.models import ArenaProfile

    rows = list(
        ArenaProfile.objects.filter(user__is_bot=False)
        .select_related("user")
        .order_by("-rating")[:top]
    )
    if not rows:
        return "Hali reyting yo'q. Birinchi duelni boshlang!"

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i + 1}."
        lines.append(
            f"{medal} *{r.user.get_full_name() or r.user.email}* — {r.rating} ELO\n"
            f"   🏆 {r.wins} g'alaba · 🔥 {r.current_win_streak} streak"
        )
    return "\n".join(lines)


def _arena_keyboard() -> InlineKeyboardMarkup:
    """Arena action keyboard."""
    from django.conf import settings as _settings
    site_url = getattr(_settings, "SITE_URL", "http://localhost:8000")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ Navbatga tushish (Web)", url=f"{site_url}/arena/")],
        [
            InlineKeyboardButton("🔗 Xona yaratish", callback_data="arena_create"),
            InlineKeyboardButton("🏆 ELO Reyting", callback_data="arena_lb"),
        ],
        [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
    ])


async def arena_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /arena — show my ELO stats + top players + actions."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    from apps.arena import services
    from apps.arena.models import ArenaProfile

    def _get_arena_data():
        profile = services.get_or_create_profile(user)
        rank = ArenaProfile.objects.filter(
            user__is_bot=False, rating__gt=profile.rating
        ).count() + 1
        return profile, rank

    profile, rank = await _run_db(_get_arena_data)

    text = (
        f"⚔️ *QUIZ ARENA*\n\n"
        f"📊 *Sizning statistikangiz:*\n"
        f"  🎯 ELO reyting: *{profile.rating}* (#{rank})\n"
        f"  🏆 G'alabalar: *{profile.wins}* ({profile.win_rate}%)\n"
        f"  🔥 Win streak: *{profile.current_win_streak}* (rekord: {profile.best_win_streak})\n"
        f"  ⚔️ Jami duellar: *{profile.duels_played}*\n"
        f"  🎯 Aniqlik: *{profile.accuracy}%*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏆 *TOP 5:*\n"
        f"{await _run_db(_arena_leaderboard_text)}\n\n"
        f"Raqib topilmasa ~15 soniyadan keyin AI bot bilan o'ynaysiz 🤖"
    )

    await send_reply(update, text, parse_mode="Markdown", reply_markup=_arena_keyboard())


async def arena_join_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /arena_join <CODE> — join a custom room by invite code."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    args = context.args if context.args else []
    if not args:
        await send_reply(
            update,
            "🔗 *Xonaga qo'shilish*\n\n"
            "Do'stingiz bergan invite kodni kiriting:\n"
            "`/arena_join KOD123`",
            parse_mode="Markdown",
        )
        return

    code = args[0].strip().upper()

    from django.conf import settings as _settings
    from apps.arena import services
    site_url = getattr(_settings, "SITE_URL", "http://localhost:8000")

    def _join():
        room, error = services.join_custom_room(code, user)
        return room, error

    room, error = await _run_db(_join)
    if room is None:
        await send_reply(
            update,
            f"❌ *Xonaga qo'shib bo'lmadi*\n\n{error or 'Kod xato yoki xona to\'la.'}\n\n"
            f"To'g'ri kod bilan qayta urinib ko'ring: `/arena_join KOD`",
            parse_mode="Markdown",
        )
        return

    await send_reply(
        update,
        f"✅ *Xonaga qo'shildingiz!*\n\n"
        f"🔑 Kod: `{room.room_code}`\n"
        f"⚔️ Duel boshlanmoqda — Web orqali kiring:\n"
        f"{site_url}/arena/{room.room_code}/",
        parse_mode="Markdown",
    )


async def arena_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle arena inline buttons (arena_create / arena_lb)."""
    query = update.callback_query
    data = query.data

    if data == "arena_create":
        user = await _get_or_create_user_async(update)
        if not user:
            await query.answer("Xatolik")
            return

        from django.conf import settings as _settings
        from apps.arena import services
        site_url = getattr(_settings, "SITE_URL", "http://localhost:8000")

        def _create():
            room = services.create_custom_room(user)
            return room

        room = await _run_db(_create)
        await query.answer()
        await query.edit_message_text(
            f"🔗 *XONA YARATILDI!*\n\n"
            f"Do'stingizga shu kodni yuboring:\n\n"
            f"`{room.room_code}`\n\n"
            f"U botga `/arena_join {room.room_code}` yozib yoki "
            f"{site_url}/arena/ sahifasida kodni kiritib qo'shiladi.\n\n"
            f"Siz duelni shu yerda kutishingiz mumkin:\n"
            f"{site_url}/arena/{room.room_code}/",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚔️ Duelni kutish", url=f"{site_url}/arena/{room.room_code}/")
            ], [
                InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")
            ]]),
        )

    elif data == "arena_lb":
        text = await _run_db(lambda: _arena_leaderboard_text(10))
        await query.answer()
        await query.edit_message_text(
            f"🏆 *ELO REYTING (TOP 10)*\n\n{text}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Orqaga", callback_data="menu_arena")
            ]]),
        )

    else:
        await query.answer()


# ---------------------------------------------------------------------------
# Safe parsing of callback payloads
# ---------------------------------------------------------------------------

def _safe_callback_int(data: str, prefix: str) -> int | None:
    """Parse an integer from a callback string, tolerating malformed payloads."""
    raw = data[len(prefix):] if data.startswith(prefix) else data
    try:
        return int(raw)
    except (ValueError, TypeError):
        logger.warning("Malformed callback payload: %r", data)
        return None


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

def setup_handlers(app) -> None:
    """Register all handlers with the Application."""
    from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

    # Global error handler — a crash in one handler must never kill the bot
    app.add_error_handler(error_handler)

    # Commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("profile", profile_handler))
    app.add_handler(CommandHandler("tests", tests_handler))
    app.add_handler(CommandHandler("results", results_handler))
    app.add_handler(CommandHandler("essays", essays_handler))
    app.add_handler(CommandHandler("leaderboard", leaderboard_handler))
    app.add_handler(CommandHandler("streak", streak_handler))
    app.add_handler(CommandHandler("daily", daily_handler))
    app.add_handler(CommandHandler("premium", premium_handler))
    app.add_handler(CommandHandler("arena", arena_handler))
    app.add_handler(CommandHandler("arena_join", arena_join_handler))

    # Arena callbacks (must be before generic callback_handler)
    app.add_handler(CallbackQueryHandler(arena_callback_handler, pattern=r"^arena_"))

    # Quiz handler (must be before generic callback_handler)
    from apps.notifications.bot.quiz import quiz_handler, quiz_callback_handler
    app.add_handler(CommandHandler("quiz", quiz_handler))
    app.add_handler(CallbackQueryHandler(quiz_callback_handler, pattern=r"^quiz_"))

    # Auth conversation handler — catches text/contact during auth flow
    # Must be before generic callback_handler but after command handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auth_conversation_handler))
    app.add_handler(MessageHandler(filters.CONTACT, auth_conversation_handler))

    # Photo handler — payment screenshots
    app.add_handler(MessageHandler(filters.PHOTO, payment_screenshot_handler))

    # Callback queries (inline keyboards) — generic
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Bot handlers registered.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Global error handler — never lets an exception crash the bot process.

    Telegram API errors that are EXPECTED under normal operation (rate
    limits 429, "bot was blocked", "chat not found") are logged at a lower
    level and skipped — they must not trigger the generic user-facing error.
    """
    error = getattr(context, "error", None)
    error_str = str(error).lower()

    # Expected API-level errors: rate limits / blocked users / deleted chats.
    # PTB's polling loop already handles 429/409 internally with retry-after;
    # these are outbound-send failures that we log and move on from.
    if isinstance(error, telegram.error.TelegramError) and any(
        marker in error_str
        for marker in (
            "429", "too many requests",
            "bot was blocked", "forbidden: bot was blocked",
            "chat not found", "user is deactivated",
        )
    ):
        logger.warning(
            "Bot API error (non-fatal): %s (update=%s)",
            error, getattr(update, "update_id", "?"),
        )
        return

    logger.exception(
        "Bot handler error while processing update: %s",
        error,
    )
    try:
        if isinstance(update, Update):
            await send_reply(
                update,
                "😕 Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring "
                "yoki /start ni bosing.",
            )
    except Exception:
        logger.exception("Error handler itself failed")


async def post_init(app) -> None:
    """Set bot commands menu after initialization."""
    await app.bot.set_my_commands([
        BotCommand("start", "Botni ishga tushirish"),
        BotCommand("help", "Yordam"),
        BotCommand("quiz", "🧠 Telegram Quiz — test topshirish"),
        BotCommand("results", "Barcha natijalar"),
        BotCommand("profile", "Shaxsiy profil"),
        BotCommand("tests", "Mavjud testlar"),
        BotCommand("essays", "Esse mavzulari"),
        BotCommand("leaderboard", "Reyting"),
        BotCommand("streak", "Kunlik streak"),
        BotCommand("daily", "Kunlik vazifalar"),
        BotCommand("premium", "Premium obuna"),
        BotCommand("arena", "⚔️ 1v1 Arena — ELO reyting"),
        BotCommand("arena_join", "Invite kod bilan xonaga qo'shilish"),
    ])
    logger.info("Bot commands menu set.")
