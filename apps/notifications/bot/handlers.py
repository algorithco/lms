"""
Telegram Bot Handlers — interactive commands for uz_essaygrader bot.

Commands:
    /start    — Welcome + auto-link telegram_chat_id
    /help     — Bot commands help
    /profile  — User stats (tests, essays, XP, certificates)
    /tests    — Available tests list
    /results  — Recent test results
    /essays   — Essay topics
    /essay    — Submit an essay (text or image/OCR)
    /plans    — Commercial plans (START / PRO)
    /buy      — Purchase a plan with Telegram Stars
    /myplan   — Current subscription status
    /limits   — Remaining commercial allowances
    /paysupport — Payment support
    /cancel   — Abandon the current interactive flow

Teacher commands (group-scoped; a teacher only ever sees their own groups):
    /groups           — My assigned groups
    /attendance       — Take today's attendance for a group
    /attendance_report— Attendance statistics for a group
    /students         — Assigned students with attendance percentages
    /essay_results    — Group essay results (aggregate header + paged rows)
    /group_report     — Combined attendance + essay report for a group

Inline Keyboards:
    - Main menu actions
    - Test list navigation
    - Essay topic selection
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

import telegram
from asgiref.sync import sync_to_async
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.access import is_platform_admin
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = logging.getLogger(__name__)


async def _require_private_chat(update: Update) -> bool:
    """Prevent personal tuition and student report details entering group chats."""
    chat = getattr(update, "effective_chat", None)
    if chat is None or getattr(chat, "type", None) == "private":
        return True
    await send_reply(
        update,
        "Shaxsiy moliyaviy va o'quvchi hisobotlari faqat bot bilan shaxsiy chatda ochiladi.",
    )
    return False


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
        user, created = get_or_create_telegram_user(
            {
                "id": tg_user.id,
                "first_name": tg_user.first_name or "",
                "last_name": tg_user.last_name or "",
            }
        )
    except TelegramIdentityUnverified:
        logger.warning(
            "Legacy Telegram identity requires verification: tg_id=%d", tg_user.id
        )
        return None
    if created:
        logger.info(
            "Bot: new user registered: tg_id=%d, user_id=%d", tg_user.id, user.id
        )
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


def _error_keyboard(retry_callback: str | None = None) -> InlineKeyboardMarkup:
    """Friendly navigation keyboard for error states."""
    buttons = []
    if retry_callback:
        buttons.append(
            [InlineKeyboardButton("🔄 Qayta urinish", callback_data=retry_callback)]
        )
    buttons.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")])
    return InlineKeyboardMarkup(buttons)


async def send_friendly_error(
    update: Update,
    message: str = "Amalni bajarishda qiyinchilik yuz berdi.",
    retry_callback: str | None = None,
) -> None:
    """Send user-friendly error with immediate navigation buttons so student is never stuck."""
    text = (
        f"💡 *Kutilmagan holat yuz berdi:*\n"
        f"{message}\n\n"
        f"Quyidagi tugmalar orqali davom etishingiz mumkin 👇"
    )
    await send_reply(
        update,
        text,
        parse_mode="Markdown",
        reply_markup=_error_keyboard(retry_callback),
    )


SUPERADMIN_TELEGRAM_ID = 5582178765


def _get_user_role(user: "User | None", tg_id: int | None = None) -> str:
    """Determine role: 'admin', 'teacher', or 'student'.

    Superadmin ID (5582178765) or platform admins always resolve to 'admin'.
    """
    from django.conf import settings as _settings

    admin_tg_id = int(getattr(_settings, "ADMIN_TELEGRAM_ID", SUPERADMIN_TELEGRAM_ID))
    if tg_id and int(tg_id) == admin_tg_id:
        return "admin"
    if not user:
        return "student"
    if (
        getattr(user, "telegram_chat_id", None)
        and int(user.telegram_chat_id) == admin_tg_id
    ):
        return "admin"
    if (
        getattr(user, "is_superuser", False)
        or (getattr(user, "role", "") or "").lower() == "admin"
        or is_platform_admin(user)
    ):
        return "admin"
    if (getattr(user, "role", "") or "").lower() == "teacher":
        return "teacher"
    return "student"


def require_role(*roles: str):
    """Decorator to enforce role-based access control (RBAC) on bot handlers and callbacks."""
    from functools import wraps

    normalized_roles = [r.lower() for r in roles]

    def decorator(handler_func):
        @wraps(handler_func)
        async def wrapper(
            update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
        ):
            try:
                chat = getattr(update, "effective_chat", None)
                if (
                    chat
                    and getattr(chat, "type", None) != "private"
                    and handler_func.__name__
                    in ("weekly_report_handler", "group_payments_handler")
                ):
                    if not await _require_private_chat(update):
                        return

                tg_user = getattr(update, "effective_user", None)
                tg_id = tg_user.id if tg_user else None
                from django.conf import settings as _settings

                admin_id = int(
                    getattr(_settings, "ADMIN_TELEGRAM_ID", SUPERADMIN_TELEGRAM_ID)
                )

                is_superadmin = tg_id is not None and int(tg_id) == admin_id

                user = await _get_or_create_user_async(update) if tg_user else None

                if user is None and not is_superadmin:
                    await send_reply(
                        update, "Hisobni aniqlab bo'lmadi. /start ni bosing."
                    )
                    return

                user_role = _get_user_role(user, tg_id)

                has_access = False
                if is_superadmin:
                    has_access = True
                elif "admin" in normalized_roles and user_role == "admin":
                    has_access = True
                elif "teacher" in normalized_roles and user_role in (
                    "teacher",
                    "admin",
                ):
                    has_access = True
                elif "student" in normalized_roles:
                    has_access = True

                if not has_access:
                    if "admin" in normalized_roles:
                        denied_msg = "⛔️ Bu bo'lim faqat administratorlar uchun!"
                    elif "teacher" in normalized_roles:
                        denied_msg = "⛔️ Bu buyruq faqat o'qituvchilar uchun!"
                    else:
                        denied_msg = "⛔️ Sizda bu amalni bajarish uchun ruxsat yo'q!"

                    if getattr(update, "callback_query", None):
                        try:
                            await update.callback_query.answer(
                                denied_msg, show_alert=True
                            )
                        except Exception:
                            pass
                        try:
                            if update.callback_query.message:
                                await update.callback_query.message.reply_text(
                                    denied_msg,
                                    reply_markup=_persistent_menu_keyboard(user_role),
                                )
                        except Exception:
                            pass
                    elif getattr(update, "message", None):
                        await update.message.reply_text(
                            denied_msg,
                            reply_markup=_persistent_menu_keyboard(user_role),
                        )
                    return

                return await handler_func(update, context, *args, **kwargs)
            except Exception as exc:
                logger.exception(
                    "Error in handler %s: %s",
                    getattr(handler_func, "__name__", "unknown"),
                    exc,
                )
                try:
                    await send_friendly_error(
                        update,
                        message="Operatsiyani bajarishda kutilmagan holat yuz berdi. Iltimos, /start ni bosing.",
                    )
                except Exception:
                    pass

        return wrapper

    return decorator


def _persistent_menu_keyboard(role: str = "student") -> ReplyKeyboardMarkup:
    """Fixed reply keyboard buttons shown at the bottom of the screen according to role."""
    norm_role = (role or "student").lower()
    if norm_role in ("admin", "superadmin"):
        return ReplyKeyboardMarkup(
            [
                [
                    KeyboardButton("📥 Yangi to'lov cheklari (Tasdiqlash)"),
                    KeyboardButton("📈 Umumiy statistika"),
                ],
                [
                    KeyboardButton("👨‍🏫 O'qituvchilarni tasdiqlash"),
                    KeyboardButton("⚙️ Tizim sozlamalari"),
                ],
                [
                    KeyboardButton("🎓 O'quvchi menyusi"),
                    KeyboardButton("👨‍🏫 O'qituvchi menyusi"),
                ],
            ],
            resize_keyboard=True,
        )
    elif norm_role == "teacher":
        return ReplyKeyboardMarkup(
            [
                [
                    KeyboardButton("📝 Yangi Mock yaratish (/newmock)"),
                    KeyboardButton("📷 Titul varaqni tekshirish"),
                ],
                [
                    KeyboardButton("👥 Mening guruhlarim"),
                    KeyboardButton("📊 O'quvchilar hisoboti (Excel)"),
                ],
                [
                    KeyboardButton("📚 Testlar bazasi"),
                    KeyboardButton("👤 Shaxsiy kabinet"),
                ],
            ],
            resize_keyboard=True,
        )
    else:
        # Default: STUDENT
        return ReplyKeyboardMarkup(
            [
                [KeyboardButton("✍️ Esse yozish"), KeyboardButton("📚 Test ishlash")],
                [
                    KeyboardButton("📝 Mock Test (#kod)"),
                    KeyboardButton("⚔️ Arena (1v1)"),
                ],
                [
                    KeyboardButton("👤 Natijalar / Profil"),
                    KeyboardButton("💳 Tariflar / Obuna"),
                ],
            ],
            resize_keyboard=True,
        )


def _student_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu inline keyboard for students."""
    from django.conf import settings as _settings

    _site_url = getattr(_settings, "SITE_URL", "https://grandec.uz").rstrip("/")
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📝 Mock Test (#kod)", callback_data="menu_mock_join"
                ),
                InlineKeyboardButton(
                    "📱 Fast CBT Test", web_app={"url": f"{_site_url}/tma/#/tests"}
                ),
            ],
            [
                InlineKeyboardButton("✍️ Esse yozish", callback_data="menu_essays"),
                InlineKeyboardButton("⚔️ Arena (1v1)", callback_data="menu_arena"),
            ],
            [
                InlineKeyboardButton("🧠 Telegram Quiz", callback_data="menu_quiz"),
                InlineKeyboardButton(
                    "📜 Sertifikatlarim (PDF)", callback_data="menu_certificates"
                ),
            ],
            [
                InlineKeyboardButton("📊 Natijalarim", callback_data="menu_results"),
                InlineKeyboardButton("👤 Profilim", callback_data="menu_profile"),
            ],
            [
                InlineKeyboardButton("💳 Tarif / To'lov", callback_data="cb_myplan"),
                InlineKeyboardButton(
                    "🏆 ELO Reyting", callback_data="menu_leaderboard"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🏆 Yakshanba Turniri", callback_data="menu_tournament"
                ),
                InlineKeyboardButton(
                    "👨‍👩‍👧 Ota-onalar nazorati", callback_data="menu_parents"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🌐 Web Platformaga o'tish", url=f"{_site_url}/dashboard/"
                ),
            ],
        ]
    )


def _teacher_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu inline keyboard for teachers."""
    from django.conf import settings as _settings

    _site_url = getattr(_settings, "SITE_URL", "https://grandec.uz").rstrip("/")
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📝 Yangi Mock yaratish (/newmock)",
                    callback_data="menu_teacher_newmock",
                ),
                InlineKeyboardButton("👥 Mening guruhlarim", callback_data="tgrplist"),
            ],
            [
                InlineKeyboardButton(
                    "📊 Excel hisobot (.xlsx)", callback_data="menu_teacher_excel"
                ),
                InlineKeyboardButton(
                    "📚 Testlar bazasi", web_app={"url": f"{_site_url}/tma/#/tests"}
                ),
            ],
            [
                InlineKeyboardButton(
                    "🗓 Bugungi davomat", callback_data="menu_teacher_attendance"
                ),
                InlineKeyboardButton(
                    "📈 Guruh hisobotlari", callback_data="menu_teacher_reports"
                ),
            ],
            [
                InlineKeyboardButton(
                    "👤 Shaxsiy kabinet", callback_data="menu_teacher_profile"
                ),
                InlineKeyboardButton(
                    "🌐 O'qituvchi boshqaruv paneli", url=f"{_site_url}/dashboard/"
                ),
            ],
        ]
    )


def _admin_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu inline keyboard for superadmin."""
    from django.conf import settings as _settings

    _site_url = getattr(_settings, "SITE_URL", "https://grandec.uz").rstrip("/")
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📥 Yangi to'lov cheklari", callback_data="adm_pending_receipts"
                ),
                InlineKeyboardButton("📈 Umumiy statistika", callback_data="adm_stats"),
            ],
            [
                InlineKeyboardButton(
                    "👨‍🏫 O'qituvchilarni tasdiqlash",
                    callback_data="adm_pending_teachers",
                ),
                InlineKeyboardButton(
                    "⚙️ Tizim sozlamalari", callback_data="adm_settings"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎓 O'quvchi menyusiga o'tish", callback_data="adm_switch_student"
                ),
                InlineKeyboardButton(
                    "👨‍🏫 O'qituvchi menyusiga o'tish",
                    callback_data="adm_switch_teacher",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🌐 Django Admin Panel", url=f"{_site_url}/admin/"
                ),
            ],
        ]
    )


def _main_menu_keyboard(role: str = "student") -> InlineKeyboardMarkup:
    """Main menu inline keyboard dispatcher by role."""
    norm_role = (role or "student").lower()
    if norm_role in ("admin", "superadmin"):
        return _admin_main_menu_keyboard()
    elif norm_role == "teacher":
        return _teacher_main_menu_keyboard()
    return _student_main_menu_keyboard()


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command — welcome + auto-link + auth token support + RBAC onboarding."""
    args = context.args if context.args else []

    if args and args[0].startswith("link_"):
        from apps.accounts.services.telegram_link import confirm_link_challenge

        tg_user = update.effective_user
        state = (
            await _run_db(
                confirm_link_challenge, args[0].removeprefix("link_"), tg_user.id
            )
            if tg_user
            else "invalid"
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

    # --- Parent linking flow: /start parent or /start parent_<code> ---
    if args and (args[0] == "parent" or args[0].startswith("parent_")):
        if args[0].startswith("parent_"):
            context.args = [args[0].removeprefix("parent_")]
        await parent_start_handler(update, context)
        return

    # --- Tournament flow: /start tournament ---
    if args and (args[0] == "tournament" or args[0].startswith("tournament_")):
        await tournament_handler(update, context)
        return

    # --- Group join link flow: /start join_<invite_code> or /start GR-XXX ---
    if args and (args[0].startswith("join_") or args[0].upper().startswith("GR-")):
        invite_code = args[0].removeprefix("join_").upper()
        from apps.courses.group_service import join_group_by_invite_code

        user = await _get_or_create_user_async(update)
        if user:
            ok, msg, joined_grp = await _run_db(
                join_group_by_invite_code, user, invite_code
            )
            if ok and joined_grp:
                await update.message.reply_text(
                    f"✅ *Guruhga muvaffaqiyatli qo'shildingiz!*\n\n"
                    f"🏫 Guruh: *{joined_grp.name}*\n"
                    f"👨‍🏫 O'qituvchi: *{joined_grp.teacher.get_full_name() or joined_grp.teacher.email}*\n\n"
                    f"⭐ *Sizga ustozingiz guruhi orqali avtomatik ravishda PRO tarifi ulandi!*\n"
                    f"(Cheksiz BMB testlari va 50 ta kunlik AI repetitor kvotasi)",
                    parse_mode="Markdown",
                    reply_markup=_persistent_menu_keyboard("student"),
                )
                return

    tg_user = update.effective_user
    if not tg_user:
        await update.message.reply_text("Xatolik yuz berdi. Qayta urinib ko'ring.")
        return

    from django.conf import settings as _settings

    admin_tg_id = int(getattr(_settings, "ADMIN_TELEGRAM_ID", SUPERADMIN_TELEGRAM_ID))
    is_superadmin = tg_user.id == admin_tg_id

    # Check if user is already registered in DB
    from apps.accounts.models import User as UserModel

    existing_user = await _run_db(
        lambda: UserModel.objects.filter(telegram_chat_id=tg_user.id).first()
    )

    # First-time user onboarding (if not superadmin and not registered yet)
    if existing_user is None and not is_superadmin:
        onboarding_text = (
            f"Assalomu alaykum, *{tg_user.first_name}*! 👋\n\n"
            f"🎓 *Ona Tili & Adabiyot* (grandec.uz) — Rasmiy ta'lim platformasiga xush kelibsiz!\n\n"
            f"Platformadagi rolingizni tanlang:"
        )
        onboarding_kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🎓 Men o'quvchiman", callback_data="role_select_student"
                    ),
                    InlineKeyboardButton(
                        "👨‍🏫 Men o'qituvchiman", callback_data="role_select_teacher"
                    ),
                ]
            ]
        )
        await update.message.reply_text(
            onboarding_text,
            parse_mode="Markdown",
            reply_markup=onboarding_kb,
        )
        return

    user = await _get_or_create_user_async(update)
    if not user:
        await update.message.reply_text("Xatolik yuz berdi. Qayta urinib ko'ring.")
        return

    role = _get_user_role(user, tg_user.id)

    if role == "admin":
        admin_welcome = (
            f"👑 *Assalomu alaykum, Administrator ({user.first_name})!*\n\n"
            f"🏢 *GRAND EDUCATION* — Boshqaruv tizimi:\n\n"
            f"• 📥 *To'lov cheklari* — Foydalanuvchilar to'lovlarini tasdiqlash\n"
            f"• 📈 *Umumiy statistika* — O'quvchilar, esselar va testlar monitoringi\n"
            f"• 👨‍🏫 *O'qituvchilarni tasdiqlash* — Yangi ustozlarni faollashtirish\n"
            f"• ⚙️ *Tizim sozlamalari* — Xavfsizlik va server holati\n\n"
            f"Boshqaruv uchun quyidagi menyudan foydalaning 👇"
        )
        await update.message.reply_text(
            admin_welcome,
            parse_mode="Markdown",
            reply_markup=_persistent_menu_keyboard("admin"),
        )
        await update.message.reply_text(
            "👑 *Administrator boshqaruv paneli:*",
            parse_mode="Markdown",
            reply_markup=_admin_main_menu_keyboard(),
        )
    elif role == "teacher":
        teacher_welcome = (
            f"👨‍🏫 *Assalomu alaykum, Ustoz {user.first_name}!* 👋\n\n"
            f"🎓 *GRAND EDUCATION* — O'qituvchilar kabinetiga xush kelibsiz.\n\n"
            f"Bu yerda siz:\n"
            f"• 📝 */newmock* — Yangi tezkor Mock test sessiyasini yaratish\n"
            f"• 👥 *Guruhlarim* — O'z guruhlaringiz, taklif kodlari (#GR-XXX)\n"
            f"• 📊 *Excel hisobot* — O'quvchilar monitoringini .xlsx formatida olish\n"
            f"• 📚 *Testlar bazasi* — Mavjud test savollari va natijalar\n"
            f"• 🗓 *Davomat* — Dars davomatini olish va qayd etish\n\n"
            f"Kerakli bo'limni tanlang 👇"
        )
        await update.message.reply_text(
            teacher_welcome,
            parse_mode="Markdown",
            reply_markup=_persistent_menu_keyboard("teacher"),
        )
        await update.message.reply_text(
            "👨‍🏫 *O'qituvchi boshqaruv paneli:*",
            parse_mode="Markdown",
            reply_markup=_teacher_main_menu_keyboard(),
        )
    else:
        # Normal Student flow
        welcome = (
            f"Salom, *{user.first_name}*! 👋\n\n"
            f"🎓 *Ona Tili & Adabiyot* — Ta'lim platformasining rasmiy boti.\n\n"
            f"Bu yerda:\n"
            f"• ✍️ *Esse yozish* (AI baholaydi, takomillashtiradi)\n"
            f"• 🧠 *Telegram Quiz* va testlar topshirish\n"
            f"• ⚔️ *Arena 1v1* duellarida bellashish\n"
            f"• 📜 *Sertifikatlarni* to'g'ridan-to'g'ri PDF yuklab olish\n"
            f"• 📊 To'lov va davomat monitoringi\n\n"
            f"Quyidagi menyudan kerakli bo'limni tanlang 👇"
        )
        await update.message.reply_text(
            welcome,
            parse_mode="Markdown",
            reply_markup=_persistent_menu_keyboard("student"),
        )
        await update.message.reply_text(
            "🎓 *Ona Tili & Adabiyot* — Boshqaruv paneli:",
            parse_mode="Markdown",
            reply_markup=_student_main_menu_keyboard(),
        )


async def _handle_auth_token(
    update: Update, context: ContextTypes.DEFAULT_TYPE, token_arg: str
) -> None:
    """Handle /start auth_<token>.

    A verified Telegram link is already sufficient to identify an existing
    account, so do not make those users share their phone again.  Phone
    sharing remains required only when the account has to be matched by its
    website profile phone (or when a new account is being created).
    """
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

    # Fast path for users who have already completed the signed Telegram link
    # challenge.  This is both safer and much less confusing than asking an
    # already-linked user for a phone number that may not be present on their
    # Telegram account.
    from apps.accounts.models import Profile
    from apps.accounts.services.telegram_identity import (
        TelegramIdentityUnverified,
        resolve_bot_auth_user,
        normalize_phone,
    )

    try:
        linked_user, how = await _run_db(resolve_bot_auth_user, tg_user.id, "")
    except TelegramIdentityUnverified as exc:
        await update.message.reply_text(str(exc))
        return
    except ValueError as exc:
        await update.message.reply_text(str(exc) or "Hisob faol emas.")
        return

    if linked_user is not None and how == "tg":

        def _linked_profile_phone():
            try:
                return normalize_phone(linked_user.profile.phone)
            except Profile.DoesNotExist:
                return ""

        profile_phone = await _run_db(_linked_profile_phone)
        context.user_data["auth_token"] = token
        await _finish_existing_account(
            update,
            context,
            token,
            linked_user,
            linked_user.get_full_name() or tg_user.first_name or "Telegram user",
            profile_phone,
        )
        return

    # Store token in context for conversation flow. Phone FIRST: an existing
    # account is matched by the verified contact number (fast code); only a
    # genuinely new number is asked for a name afterwards.
    context.user_data["auth_token"] = token
    context.user_data["auth_state"] = "awaiting_phone"

    # Start conversation: ask for the verified contact number
    await update.message.reply_text(
        "🔐 *Telegram orqali kirish*\n\n"
        "Hisobingizni topish uchun telefon raqamingizni ulashing:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(text="📱 Telefonni yuborish", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    logger.info("TG auth conversation started: tg_id=%d", tg_user.id if tg_user else 0)


def _clear_auth_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Drop all Telegram-auth conversation keys."""
    for key in ("auth_state", "auth_token", "auth_name", "auth_phone"):
        context.user_data.pop(key, None)


def _complete_auth_login(auth_token_str: str, user, full_name: str, clean_phone: str):
    """Persist verification + mint the 6-digit code. Returns code or None.

    Shared by the fast path (existing account) and the new-account path.
    Callers must have checked phone uniqueness first.
    """
    from django.utils import timezone
    from apps.accounts.models import Profile
    from apps.notifications.models import TelegramAuthToken

    if user is None or not user.is_active:
        return None

    # Lock the token so a duplicate Telegram update cannot replace a code
    # after the first update has already verified it.
    with transaction.atomic():
        try:
            at = TelegramAuthToken.objects.select_for_update().get(
                token=auth_token_str,
            )
        except TelegramAuthToken.DoesNotExist:
            return None
        if at.is_expired or at.consumed_at or at.is_verified:
            return None

        has_verified_phone = bool(clean_phone)
        at.full_name = full_name
        at.phone_number = clean_phone if has_verified_phone else ""
        at.phone_verified = has_verified_phone
        at.conversation_state = "code_displayed"
        code = at.generate_short_code()
        at.user = user
        at.telegram_chat_id = getattr(user, "telegram_chat_id", None)
        at.is_verified = True
        at.verified_at = timezone.now()
        at.save(
            update_fields=[
                "full_name",
                "phone_number",
                "phone_verified",
                "conversation_state",
                "short_code",
                "user",
                "telegram_chat_id",
                "is_verified",
                "verified_at",
            ]
        )

        profile, _ = Profile.objects.get_or_create(user=user)
        if has_verified_phone and (not profile.phone or profile.phone == clean_phone):
            profile.phone = clean_phone
            profile.save(update_fields=["phone"])
    return code


async def _send_auth_code(
    update: Update, full_name: str, clean_phone: str, code: str, is_new: bool
) -> None:
    """Deliver the 6-digit website-login code (contact keyboard removed)."""
    code_display = "  ".join(code)
    identity_line = (
        f"📱 Telefon: `{clean_phone}` (✅ tasdiqlangan)"
        if clean_phone
        else "🔗 Telegram hisobingiz tasdiqlandi"
    )
    hello = (
        "🎉 *Ma'lumotlar saqlandi!*\n\n"
        if is_new
        else f"🎉 *Xush kelibsiz, {full_name}!*\n\n"
    )
    tail = (
        f"👤 Ism: *{full_name}*\n"
        f"{identity_line}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 *SIZNING KODINGIZ:*\n\n"
        f"`{code_display}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏰ Kod 10 daqiqa ichida eskiradi.\n\n"
        f"🌐 Veb-saytda shu kodni kiriting:\n"
        f'1. "Telegram orqali kirish" tugmasini bosing\n'
        f"2. Kodni kiriting\n"
        f"3. Tizimga kiring!"
    )
    if is_new:
        tail += "\n\n_Yangi hisob ochildi._"
    await update.message.reply_text(
        hello + tail,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


async def auth_conversation_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle text messages during Telegram auth or essay submission."""
    essay_state = context.user_data.get("bot_essay_state")
    if essay_state in ("awaiting_text", "awaiting_submission"):
        await _handle_bot_essay_text(update, context)
        return
    if essay_state == ESSAY_OCR_EDIT_STATE:
        await _handle_ocr_corrected_text(update, context)
        return

    # -----------------------------------------------------------------------
    # Persistent Keyboard Button Taps & RBAC Enforcement
    # -----------------------------------------------------------------------
    raw_text = (getattr(update.message, "text", "") or "").strip()

    # --- Student Persistent Buttons ---
    if raw_text in ("✍️ Esse yozish", "✍️ Esse"):
        await essays_handler(update, context)
        return
    elif raw_text in (
        "📚 Test ishlash",
        "📚 Test topshirish",
        "🧠 Test / Quiz",
        "🧠 Quiz",
        "📝 Testlar",
    ):
        await tests_handler(update, context)
        return
    elif raw_text in (
        "📷 Titul varaqni tekshirish",
        "📷 Titul varaq",
        "/omr",
        "Titul varaq",
    ):
        await omr_scan_prompt_handler(update, context)
        return
    elif raw_text in ("⚔️ Arena (1v1)", "⚔️ Arena"):
        await arena_handler(update, context)
        return
    elif raw_text in ("📜 Sertifikatlarim", "📜 Sertifikatlar"):
        await certificates_handler(update, context)
        return
    elif raw_text in (
        "💳 Tariflar / Obuna",
        "💳 Tariflar",
        "💳 Obuna",
        "💳 Mening tarifim",
        "💳 To'lov",
        "💳 Tarif",
    ):
        await plans_and_payment_handler(update, context)
        return
    elif raw_text in (
        "👤 Natijalar / Profil",
        "👤 Profil",
        "👤 Profilim",
        "📊 Natijalarim",
        "📊 Natijalar",
    ):
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role == "teacher":
            await teacher_profile_handler(update, context)
        elif role == "admin":
            await admin_panel_handler(update, context)
        else:
            await profile_handler(update, context)
        return
    elif raw_text in ("📅 Davomat", "📅 Davomatim"):
        await myattendance_handler(update, context)
        return
    elif raw_text in (
        "👨‍👩‍👧 Ota-ona nazorati",
        "👨‍👩‍👧 Ota-onani ulash",
        "Ota-ona nazorati",
        "Ota-ona",
    ):
        await parent_start_handler(update, context)
        return
    elif raw_text in (
        "🏆 Yakshanba Turniri",
        "🏆 Turnir",
        "Yakshanba Turniri",
        "Turnir",
    ):
        await tournament_handler(update, context)
        return
    elif raw_text in ("📝 Mock Test (#kod)", "📝 Mock Test", "Mock Test"):
        context.user_data["awaiting_mock_code"] = True
        text = (
            "📝 *MILLIY SERTIFIKAT MOCK TESTGA ULANISH*\n\n"
            "Ustozingiz bergan Mock kodini botga yuboring:\n"
            "Masalan: `#MOCK-401` yoki `MOCK-401`\n\n"
            "📌 Kodni yozib yuborganingizdan so'ng, test darhol boshlanadi va rasmiy BMB darajangiz (A+, A, B+...) hisoblab beriladi."
        )
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    # --- Teacher Persistent Buttons ---
    elif raw_text in ("📝 Yangi Mock yaratish (/newmock)", "📝 Yangi Mock yaratish"):
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role not in ("teacher", "admin"):
            await update.message.reply_text(
                "⛔️ Bu buyruq faqat o'qituvchilar uchun!",
                reply_markup=_persistent_menu_keyboard(role),
            )
            return
        await newmock_handler(update, context)
        return
    elif raw_text in ("👥 Mening guruhlarim", "👥 Guruhlarim", "Mening guruhlarim"):
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role not in ("teacher", "admin"):
            await update.message.reply_text(
                "⛔️ Bu buyruq faqat o'qituvchilar uchun!",
                reply_markup=_persistent_menu_keyboard(role),
            )
            return
        await groups_handler(update, context)
        return
    elif raw_text in (
        "📊 O'quvchilar hisoboti (Excel)",
        "📊 O'quvchilar hisoboti",
        "O'quvchilar hisoboti (Excel)",
    ):
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role not in ("teacher", "admin"):
            await update.message.reply_text(
                "⛔️ Bu buyruq faqat o'qituvchilar uchun!",
                reply_markup=_persistent_menu_keyboard(role),
            )
            return
        await teacher_excel_report_handler(update, context)
        return
    elif raw_text in ("📚 Testlar bazasi", "Testlar bazasi"):
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role not in ("teacher", "admin"):
            await update.message.reply_text(
                "⛔️ Bu buyruq faqat o'qituvchilar uchun!",
                reply_markup=_persistent_menu_keyboard(role),
            )
            return
        await teacher_test_bank_handler(update, context)
        return
    elif raw_text in ("👤 Shaxsiy kabinet", "Shaxsiy kabinet"):
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role == "teacher":
            await teacher_profile_handler(update, context)
            return
        elif role == "admin":
            await admin_panel_handler(update, context)
            return
        else:
            await profile_handler(update, context)
            return

    # --- Superadmin Persistent Buttons ---
    elif raw_text in (
        "📥 Yangi to'lov cheklari (Tasdiqlash)",
        "📥 Yangi to'lov cheklari",
        "Yangi to'lov cheklari",
    ):
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role != "admin":
            await update.message.reply_text(
                "⛔️ Bu bo'lim faqat administratorlar uchun!",
                reply_markup=_persistent_menu_keyboard(role),
            )
            return
        await admin_pending_receipts_handler(update, context)
        return
    elif raw_text in ("📈 Umumiy statistika", "Umumiy statistika"):
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role != "admin":
            await update.message.reply_text(
                "⛔️ Bu bo'lim faqat administratorlar uchun!",
                reply_markup=_persistent_menu_keyboard(role),
            )
            return
        await admin_stats_handler(update, context)
        return
    elif raw_text in ("👨‍🏫 O'qituvchilarni tasdiqlash", "O'qituvchilarni tasdiqlash"):
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role != "admin":
            await update.message.reply_text(
                "⛔️ Bu bo'lim faqat administratorlar uchun!",
                reply_markup=_persistent_menu_keyboard(role),
            )
            return
        await admin_pending_teachers_handler(update, context)
        return
    elif raw_text in ("⚙️ Tizim sozlamalari", "Tizim sozlamalari"):
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role != "admin":
            await update.message.reply_text(
                "⛔️ Bu bo'lim faqat administratorlar uchun!",
                reply_markup=_persistent_menu_keyboard(role),
            )
            return
        await admin_settings_handler(update, context)
        return
    elif raw_text == "🎓 O'quvchi menyusi":
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role != "admin":
            await update.message.reply_text(
                "⛔️ Bu buyruq faqat administratorlar uchun!"
            )
            return
        await update.message.reply_text(
            "🎓 O'quvchi rejimi ko'rinishi faollashtirildi 👇",
            reply_markup=_persistent_menu_keyboard("student"),
        )
        await update.message.reply_text(
            "🎓 *Ona Tili & Adabiyot* — O'quvchi boshqaruv paneli:",
            parse_mode="Markdown",
            reply_markup=_student_main_menu_keyboard(),
        )
        return
    elif raw_text == "👨‍🏫 O'qituvchi menyusi":
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role != "admin":
            await update.message.reply_text(
                "⛔️ Bu buyruq faqat administratorlar uchun!"
            )
            return
        await update.message.reply_text(
            "👨‍🏫 O'qituvchi rejimi ko'rinishi faollashtirildi 👇",
            reply_markup=_persistent_menu_keyboard("teacher"),
        )
        await update.message.reply_text(
            "👨‍🏫 *GRAND EDUCATION* — O'qituvchi boshqaruv paneli:",
            parse_mode="Markdown",
            reply_markup=_teacher_main_menu_keyboard(),
        )
        return
    elif raw_text in ("👑 Admin menyusi", "👑 Admin paneli"):
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role != "admin":
            await update.message.reply_text(
                "⛔️ Bu bo'lim faqat administratorlar uchun!"
            )
            return
        await admin_panel_handler(update, context)
        return

    # Check for awaiting_create_group state
    if context.user_data.get("awaiting_create_group"):
        context.user_data.pop("awaiting_create_group", None)
        user = await _get_or_create_user_async(update)
        group_name = raw_text.strip()
        if len(group_name) < 2:
            await update.message.reply_text("Iltimos, guruh nomini to'liqroq kiriting.")
            return
        from apps.courses.models import StudentGroup

        grp = await _run_db(
            lambda: StudentGroup.objects.create(teacher=user, name=group_name)
        )
        invite_code = grp.invite_code or f"GR-{grp.id}"
        await update.message.reply_text(
            f"✅ *Yangi guruh muvaffaqiyatli ochildi!*\n\n"
            f"🏫 Guruh nomi: *{grp.name}*\n"
            f"📌 Taklif kodi: `#{invite_code}`\n\n"
            f"O'quvchilaringizga ushbu kodni yuboring. O'quvchi botga `#{invite_code}` deb yozishi "
            f"bilanoq guruhga qo'shiladi va unga avtomatik PRO tarifi beriladi!",
            parse_mode="Markdown",
            reply_markup=_persistent_menu_keyboard("teacher"),
        )
        return

    # Check for #MOCK-XXX or MOCK-XXX code input or awaiting_mock_code
    upper_raw = raw_text.upper().strip()
    is_awaiting_mock = bool(context.user_data.get("awaiting_mock_code"))
    if (
        upper_raw.startswith("#MOCK-")
        or (upper_raw.startswith("MOCK-") and len(upper_raw) >= 6)
        or is_awaiting_mock
    ):

        def _load_mock():
            from apps.tests.mock_service import find_mock_by_code

            m = find_mock_by_code(raw_text)
            if not m:
                return None
            return {
                "id": m.id,
                "title": m.title,
                "total_questions": m.total_questions,
                "time_limit_minutes": m.time_limit_minutes,
            }

        mock_test = await _run_db(_load_mock)
        if mock_test:
            context.user_data.pop("awaiting_mock_code", None)
            text = (
                f"📋 *MILLIY SERTIFIKAT MOCK TEST TOPILDI*\n\n"
                f"📌 Test: *{mock_test['title']}*\n"
                f"🔢 Savollar soni: *{mock_test['total_questions']} ta*\n"
                f"⏱ Vaqt: *{mock_test['time_limit_minutes']} daqiqa*\n"
                f"🎯 Rasmiy BMB darajalari baholanadi (A+, A, B+, B, C+, C).\n\n"
                f"Testni Telegramda boshlashga tayyormisiz?"
            )
            buttons = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🚀 Testni boshlash",
                            callback_data=f"quiz_start_{mock_test['id']}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ Bekor qilish", callback_data="menu_main"
                        )
                    ],
                ]
            )
            await update.message.reply_text(
                text, parse_mode="Markdown", reply_markup=buttons
            )
            return
        elif (
            is_awaiting_mock
            or upper_raw.startswith("#MOCK-")
            or upper_raw.startswith("MOCK-")
        ):
            context.user_data.pop("awaiting_mock_code", None)
            await update.message.reply_text(
                f"❌ '{raw_text}' kodi bo'yicha Mock test topilmadi.\n"
                f"Iltimos, ustozingiz bergan kodni to'g'ri kiritganingizni tekshiring (masalan: `#MOCK-401`).",
                parse_mode="Markdown",
            )
            return

    # Check for #GR-XXX or GR-XXX group invite code input
    if upper_raw.startswith("#GR-") or (
        upper_raw.startswith("GR-") and len(upper_raw) >= 5
    ):
        clean_code = upper_raw.removeprefix("#").strip()
        from apps.courses.group_service import join_group_by_invite_code

        user = await _get_or_create_user_async(update)
        success, msg, grp = await _run_db(join_group_by_invite_code, user, clean_code)
        if success and grp:
            teacher_name = grp.teacher.get_full_name() or grp.teacher.email
            await update.message.reply_text(
                f"✅ *Guruhga muvaffaqiyatli qo'shildingiz!*\n\n"
                f"🏫 Guruh nomi: *{grp.name}*\n"
                f"👨‍🏫 O'qituvchi: *{teacher_name}*\n\n"
                f"⭐ *Sizga ustozingiz guruhi orqali PRO tarifi faollashtirildi!*\n"
                f"• Cheksiz BMB mock testlari va diagnostikalar\n"
                f"• Kunlik 50 ta sun'iy intellekt (AI repetitor) tahlili\n"
                f"• Barcha test va esse natijalaringiz ustozingiz hisobotida aks etadi.",
                parse_mode="Markdown",
                reply_markup=_persistent_menu_keyboard("student"),
            )
            return
        else:
            await update.message.reply_text(
                f"❌ '{raw_text}' kodi bo'yicha guruh topilmadi yoki ulanishda xatolik yuz berdi ({msg}).\n\n"
                f"Iltimos, ustozingiz bergan taklif kodini to'g'ri kiritganingizni tekshiring (masalan: `#GR-101`).",
                parse_mode="Markdown",
                reply_markup=_persistent_menu_keyboard("student"),
            )
            return

    # Check for teacher phone verification contact
    contact = getattr(update.message, "contact", None)
    if contact and context.user_data.get("awaiting_teacher_contact"):
        context.user_data.pop("awaiting_teacher_contact", None)
        contact_phone = getattr(contact, "phone_number", "") or ""
        import re

        digits = re.sub(r"\D", "", contact_phone)
        clean_9 = digits[-9:] if len(digits) >= 9 else ""

        def _verify_teacher_phone(phone_tail: str, chat_id: int):
            from apps.accounts.models import User as UserModel

            t = UserModel.objects.filter(
                profile__phone__endswith=phone_tail, role=UserModel.Role.TEACHER
            ).first()
            if t:
                t.telegram_chat_id = chat_id
                t.telegram_identity_verified_at = timezone.now()
                t.save(
                    update_fields=["telegram_chat_id", "telegram_identity_verified_at"]
                )
                return t
            return None

        t_user = await _run_db(_verify_teacher_phone, clean_9, update.effective_user.id)
        if t_user:
            await update.message.reply_text(
                f"✅ *O'qituvchi hisobingiz muvaffaqiyatli tasdiqlandi!*\n\n"
                f"Xush kelibsiz, Ustoz {t_user.first_name}!",
                parse_mode="Markdown",
                reply_markup=_persistent_menu_keyboard("teacher"),
            )
            await update.message.reply_text(
                "👨‍🏫 *O'qituvchi boshqaruv paneli:*",
                parse_mode="Markdown",
                reply_markup=_teacher_main_menu_keyboard(),
            )
            return
        else:
            await update.message.reply_text(
                "Telefon raqamingiz bo'yicha bazada o'qituvchi hisobi topilmadi. "
                "Arizangiz administrator tomonidan tasdiqlanishini kuting.",
                reply_markup=_persistent_menu_keyboard("student"),
            )
            return

    # Check for 6-digit parent code input or awaiting_parent_code
    is_awaiting_parent = bool(context.user_data.get("awaiting_parent_code"))
    if contact and is_awaiting_parent:
        contact_phone = getattr(contact, "phone_number", "") or ""
        import re

        digits = re.sub(r"\D", "", contact_phone)
        clean_9 = digits[-9:] if len(digits) >= 9 else ""

        def _link_by_phone(phone_tail: str, chat_id: int):
            from apps.accounts.models import ParentStudentRelation

            rels = ParentStudentRelation.objects.filter(
                parent_phone__endswith=phone_tail
            ).select_related("student")
            if not rels.exists():
                return None
            names = []
            for r in rels:
                r.parent_telegram_id = chat_id
                r.is_verified = True
                r.save(
                    update_fields=["parent_telegram_id", "is_verified", "updated_at"]
                )
                names.append(r.student.get_full_name() or r.student.email)
            return names

        linked_names = await _run_db(_link_by_phone, clean_9, update.effective_user.id)
        context.user_data.pop("awaiting_parent_code", None)
        if linked_names:
            names_str = ", ".join(linked_names)
            await update.message.reply_text(
                f"✅ <b>Telefon raqamingiz muvaffaqiyatli bog'landi!</b>\n\n"
                f"Farzandingiz: <b>{names_str}</b>\n\n"
                f"Test natijalari va haftalik hisobotlar endi ushbu chatga yuboriladi.",
                parse_mode="HTML",
                reply_markup=_persistent_menu_keyboard(),
            )
            return
        else:
            await update.message.reply_text(
                "Telefon raqamingiz bo'yicha kutilayotgan o'quvchi topilmadi. "
                "Iltimos, farzandingizdan 6 xonali tasdiqlash kodini olib yuboring (masalan: <code>/parent_start 123456</code>).",
                parse_mode="HTML",
                reply_markup=_persistent_menu_keyboard(),
            )
            return

    if raw_text.isdigit() and len(raw_text) == 6:

        def _check_and_link(code_val: str, chat_id: int):
            from apps.accounts.models import ParentStudentRelation

            rel = (
                ParentStudentRelation.objects.filter(verification_code=code_val)
                .select_related("student")
                .first()
            )
            if not rel:
                return None
            rel.parent_telegram_id = chat_id
            rel.is_verified = True
            rel.save(update_fields=["parent_telegram_id", "is_verified", "updated_at"])
            return rel.student.get_full_name() or rel.student.email

        student_name = await _run_db(
            _check_and_link, raw_text, update.effective_user.id
        )
        if student_name:
            context.user_data.pop("awaiting_parent_code", None)
            await update.message.reply_text(
                f"✅ <b>Muvaffaqiyatli bog'landi!</b>\n\n"
                f"Siz o'quvchi <b>{student_name}</b> ga ota-ona sifatida biriktirildingiz.\n\n"
                f"Endi barcha test va mock natijalari hamda haftalik hisobotlar ushbu chatga boradi.",
                parse_mode="HTML",
                reply_markup=_persistent_menu_keyboard(),
            )
            return

    # Teacher /newmock command with strict RBAC
    if raw_text.lower().startswith("/newmock") or raw_text.lower().startswith(
        "#newmock"
    ):
        user = await _get_or_create_user_async(update)
        role = _get_user_role(
            user, update.effective_user.id if update.effective_user else None
        )
        if role not in ("teacher", "admin"):
            await update.message.reply_text(
                "⛔️ Bu buyruq faqat o'qituvchilar uchun!",
                reply_markup=_persistent_menu_keyboard(role),
            )
            return

        parts = raw_text.split(maxsplit=1)
        if len(parts) < 2:
            await update.message.reply_text(
                "Ustoz, kalitlarni quyidagi formatda yuboring:\n"
                "`/newmock 1a2b3c4d5a...40b`\n\n"
                "Masalan: 40 ta savol uchun `1a2b3c4d...`",
                parse_mode="Markdown",
            )
            return
        key_str = parts[1].strip()
        from apps.tests.mock_service import create_quick_mock

        try:
            res = await _run_db(create_quick_mock, user, key_str)
            code = res["mock_code"]
            await update.message.reply_text(
                f"✅ *Mock sessiya muvaffaqiyatli yaratildi!*\n\n"
                f"📌 Test kodi: `{code}`\n"
                f"🔢 Savollar: *{res['total_questions']} ta*\n"
                f"⏱ Vaqt: *{res['time_limit_minutes']} daqiqa*\n\n"
                f"O'quvchilaringizga ushbu kodni yuboring:\n"
                f"👉 O'quvchi botga `{code}` deb yozsa, darhol test boshlanadi!",
                parse_mode="Markdown",
            )
        except Exception as e:
            await update.message.reply_text(f"Xatolik: {e}")
        return

    from django.utils import timezone
    from apps.notifications.models import TelegramAuthToken

    auth_state = context.user_data.get("auth_state")
    if not auth_state or auth_state == "idle":
        help_text = (
            "👋 Assalomu alaykum! Kerakli bo'limni tanlash uchun quyidagi menyu tugmalaridan foydalaning:\n\n"
            "✍️ *Esse yozish* — AI orqali 12 mezonli esse tahlili va tahriri\n"
            "📚 *Test ishlash* — Fast CBT Mini App yoki Telegram chat orqali quiz\n"
            "📝 *Mock Test (#kod)* — Ustozingiz kodi orqali mock imtihon\n"
            "⚔️ *Arena (1v1)* — Boshqa o'quvchilar bilan real vaqtda bellashuv\n"
            "👤 *Natijalar / Profil* — Ballar, sertifikatlar va shaxsiy statistika\n"
            "💳 *Tariflar / Obuna* — Starter va Premium obunalar hamda to'lov"
        )
        await update.message.reply_text(
            help_text,
            parse_mode="Markdown",
            reply_markup=_persistent_menu_keyboard(),
        )
        return

    auth_token_str = context.user_data.get("auth_token")
    if not auth_token_str:
        return

    text = (update.message.text or "").strip()
    tg_user = update.effective_user

    if auth_state == "awaiting_name":
        # Name for a NEW account — the verified phone is already stored.
        if update.message.contact:
            await update.message.reply_text(
                "Iltimos, ism-familiyangizni matn bilan yozing."
            )
            return
        if len(text) < 3 or len(text) > 100:
            await update.message.reply_text(
                "Iltimos, to'liq ism-familiyani kiriting (3-100 belgi)."
            )
            return
        clean_phone = context.user_data.get("auth_phone", "")
        if not clean_phone:
            _clear_auth_state(context)
            await update.message.reply_text(
                "Sessiya eskirgan. Veb-saytda qaytadan 'Telegram orqali kirish' tugmasini bosing.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return
        user = await _get_or_create_user_async(update)
        if user is None:
            _clear_auth_state(context)
            await update.message.reply_text(
                "Telegram hisobingiz bog'lanishini qayta tasdiqlang yoki administratorga murojaat qiling.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return
        name_parts = text.split(" ", 1)
        user.first_name = name_parts[0][:150]
        user.last_name = (name_parts[1] if len(name_parts) > 1 else "")[:150]
        await _run_db(user.save, update_fields=["first_name", "last_name"])
        await _finish_new_account(
            update, context, auth_token_str, user, text, clean_phone
        )
        return

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
                        [
                            [
                                KeyboardButton(
                                    text="📱 Telefonni yuborish", request_contact=True
                                )
                            ]
                        ],
                        resize_keyboard=True,
                        one_time_keyboard=True,
                    ),
                )
                return
            clean_phone = (
                contact.phone_number.replace(" ", "")
                .replace("-", "")
                .replace("(", "")
                .replace(")", "")
            )
            if not _re.fullmatch(r"\+?\d{7,15}", clean_phone):
                await update.message.reply_text(
                    "Noto'g'ri telefon raqam. Iltimos, tugmani qayta bosing.",
                    reply_markup=ReplyKeyboardMarkup(
                        [
                            [
                                KeyboardButton(
                                    text="📱 Telefonni yuborish", request_contact=True
                                )
                            ]
                        ],
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

        # Match the verified number against existing accounts FIRST — a
        # website-registered user must log into THEIR account, not get a new
        # tg_* duplicate. Only a genuinely new number proceeds to name.
        from apps.accounts.services.telegram_identity import (
            TelegramAuthAmbiguous,
            TelegramAuthConflict,
            TelegramIdentityUnverified,
            find_users_by_phone,
            resolve_bot_auth_user,
        )

        try:
            user, _how = await _run_db(resolve_bot_auth_user, tg_user.id, clean_phone)
        except (
            TelegramAuthConflict,
            TelegramAuthAmbiguous,
            TelegramIdentityUnverified,
        ) as exc:
            _clear_auth_state(context)
            await update.message.reply_text(
                str(exc), reply_markup=ReplyKeyboardRemove()
            )
            return
        except ValueError as exc:
            _clear_auth_state(context)
            await update.message.reply_text(
                str(exc) or "Hisob faol emas.", reply_markup=ReplyKeyboardRemove()
            )
            return

        if user is None:
            # New number — remember it and ask for a name to open an account.
            context.user_data["auth_phone"] = clean_phone
            context.user_data["auth_state"] = "awaiting_name"
            await update.message.reply_text(
                "Bu raqamda hisob topilmadi.\n\n"
                "Yangi hisob ochish uchun to'liq ism-familiyangizni yozing:\n"
                "(Masalan: Ali Karimov)",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        # Existing account (Telegram link or phone match): fast code.
        await _finish_existing_account(
            update,
            context,
            auth_token_str,
            user,
            user.get_full_name() or tg_user.first_name or "",
            clean_phone,
        )
        return


async def _finish_existing_account(
    update, context, auth_token_str, user, full_name, clean_phone
) -> None:
    """Complete bot login for a matched account: uniqueness guard + code."""
    from apps.accounts.services.telegram_identity import find_users_by_phone

    tg_user = update.effective_user

    def _phone_taken_by_other():
        return any(u.pk != user.pk for u in find_users_by_phone(clean_phone))

    if await _run_db(_phone_taken_by_other):
        _clear_auth_state(context)
        await update.message.reply_text(
            "Bu telefon raqami boshqa hisobga bog'langan. Boshqa raqam bilan urinib ko'ring yoki administratorga murojaat qiling.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    code = await _run_db(
        _complete_auth_login, auth_token_str, user, full_name, clean_phone
    )
    if code is None:
        _clear_auth_state(context)
        await update.message.reply_text(
            "❌ Token eskirgan yoki topilmadi.\n"
            "Veb-saytda qaytadan 'Telegram orqali kirish' tugmasini bosing."
        )
        return

    await _send_auth_code(update, full_name, clean_phone, code, is_new=False)
    _clear_auth_state(context)
    logger.info(
        "TG auth fast code: user_id=%s, tg_id=%s",
        user.pk,
        tg_user.id if tg_user else "?",
    )


async def _finish_new_account(
    update, context, auth_token_str, user, full_name, clean_phone
) -> None:
    """Complete bot login for a just-provisioned account."""
    from apps.accounts.services.telegram_identity import find_users_by_phone

    tg_user = update.effective_user

    def _phone_taken_by_other():
        return any(u.pk != user.pk for u in find_users_by_phone(clean_phone))

    if await _run_db(_phone_taken_by_other):
        _clear_auth_state(context)
        await update.message.reply_text(
            "Bu telefon raqami boshqa hisobga bog'langan. Boshqa raqam bilan urinib ko'ring yoki administratorga murojaat qiling.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    code = await _run_db(
        _complete_auth_login, auth_token_str, user, full_name, clean_phone
    )
    if code is None:
        _clear_auth_state(context)
        await update.message.reply_text(
            "❌ Token eskirgan yoki topilmadi.\n"
            "Veb-saytda qaytadan 'Telegram orqali kirish' tugmasini bosing."
        )
        return

    await _send_auth_code(update, full_name, clean_phone, code, is_new=True)
    _clear_auth_state(context)
    logger.info(
        "TG auth code generated: user=%s, tg_id=%s",
        full_name,
        tg_user.id if tg_user else "?",
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
        "/daily — *Kunlik vazifalar*\n"
        "/mytuition — Kurs to'lovlari (o'quvchi / tasdiqlangan ota-ona)\n\n"
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
            "graded_count": essays.filter(status="graded").count(),
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
    """Handle /tests command & '📚 Test ishlash' menu button."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(
            update, "Xatolik yuz berdi. Iltimos, /start buyrug'ini yuboring."
        )
        return

    from django.conf import settings as _settings

    site_url = getattr(_settings, "SITE_URL", "https://grandec.uz").rstrip("/")

    text = (
        "📚 *ONA TILI VA ADABIYOTIDAN TEST TOPSHIRISH*\n\n"
        "O'zingizga qulay test formatini tanlang:\n\n"
        "1️⃣ *📱 Fast CBT (Telegram Mini App)* — Zamonaviy '1 tadan ishlash' interfeysi. "
        "Telegram ichida sahifadan chiqmasdan xuddi veb-saytdagidek test topshirish.\n\n"
        "2️⃣ *🧠 Telegram Chat Quiz* — Rasmiy Telegram so'rovnoma formatida savollar birma-bir beriladi. "
        "BMB shkalasi (A+, A, B...) hisoblanadi, AI xatolar tahlili va PDF sertifikat taqdim etiladi.\n\n"
        "3️⃣ *📝 Mock Test (#kod)* — Ustozingiz yoki repetitoringiz bergan maxsus kod orqali imtihon topshirish."
    )
    buttons = [
        [
            InlineKeyboardButton(
                "📱 Fast CBT (Mini App)", web_app={"url": f"{site_url}/tma/#/tests"}
            )
        ],
        [InlineKeyboardButton("🧠 Telegram Chat Quiz", callback_data="menu_quiz")],
        [
            InlineKeyboardButton(
                "📝 Mock Test (#kod orqali)", callback_data="menu_mock_join"
            )
        ],
        [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
    ]
    await send_reply(
        update,
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------------------------------------------------------------------------
# /results — Barcha natijalar (test + esse + tahlil)
# ---------------------------------------------------------------------------


async def _show_students_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE, teacher
) -> None:
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
        test_stats = {r["student_id"]: r for r in test_rows}

        # Aggregated graded-essay stats per student
        essay_rows = (
            EssaySubmission.objects.filter(student__role="student", status="graded")
            .values("student_id")
            .annotate(
                essay_count=Count("id"),
                essay_avg=Coalesce(Avg("total_score"), Value(0)),
            )
        )
        essay_stats = {r["student_id"]: r for r in essay_rows}

        overview = []
        for student in User.objects.filter(role="student").order_by("first_name"):
            t = test_stats.get(student.id, {})
            e = essay_stats.get(student.id, {})
            test_count = t.get("test_count", 0)
            essay_count = e.get("essay_count", 0)

            if test_count > 0 or essay_count > 0:
                overview.append(
                    {
                        "id": student.id,
                        "name": student.get_full_name() or student.email,
                        "test_count": test_count,
                        "test_avg": round(float(t.get("test_avg") or 0), 1),
                        "test_passed": t.get("test_passed", 0),
                        "essay_count": essay_count,
                        "essay_avg": round(float(e.get("essay_avg") or 0), 1),
                    }
                )

        # Sort by overall score (descending)
        overview.sort(
            key=lambda x: (x["test_avg"] + x["essay_avg"] * 100 / 24) / 2, reverse=True
        )
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
        medal = medals[i] if i < 3 else f"{i + 1}."
        grade = (
            "A"
            if s["test_avg"] >= 80
            else "B"
            if s["test_avg"] >= 60
            else "C"
            if s["test_avg"] >= 40
            else "D"
        )
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
        buttons.append(
            [
                InlineKeyboardButton(
                    f"👤 {s['name'][:25]}", callback_data=f"student_result_{s['id']}"
                )
            ]
        )
    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")])

    await send_reply(
        update,
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def _show_student_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE, student_id: int
) -> None:
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
            test_avg = round(
                float(all_tests.aggregate(avg=Avg("percentage"))["avg"] or 0), 1
            )
            test_passed = all_tests.filter(is_passed=True).count()

        essay_avg = 0
        essay_count = all_essays.count()
        if essay_count > 0:
            essay_avg = round(
                float(all_essays.aggregate(avg=Avg("total_score"))["avg"] or 0), 1
            )

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
            lines.append(f"{icon} *{r.test.title}* — {r.percentage}%")
        lines.append(
            f"\n📊 O'rtacha: *{data['test_avg']}%* ({data['test_passed']}/{data['test_total']} o'tilgan)"
        )
    else:
        lines.append("📝 Testlar: yo'q")

    # Essay results
    if data["essay_results"]:
        lines.append("\n✍️ *ESSE NATIJALARI*\n")
        for e in data["essay_results"]:
            topic = e.topic.title if e.topic else "?"
            score = float(e.total_score) if e.total_score else 0
            lines.append(f"• *{topic}* — {score}/24")
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
            grade = (
                "A"
                if score >= 20
                else "B"
                if score >= 16
                else "C"
                if score >= 12
                else "D"
                if score >= 8
                else "F"
            )

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

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📝 Testlar", callback_data="menu_tests"),
                InlineKeyboardButton("✍️ Esselar", callback_data="menu_essays"),
            ],
            [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
        ]
    )

    await send_reply(update, text, parse_mode="Markdown", reply_markup=keyboard)


# ---------------------------------------------------------------------------
# /essay_submit — submit free-form essay directly to the canonical grader
# ---------------------------------------------------------------------------


async def essay_submit_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Start the bot essay flow; /essay_submit <text> also submits directly."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    supplied_text = " ".join(context.args or []).strip()
    if supplied_text:
        await _submit_bot_essay(update, context, supplied_text)
        return

    context.user_data["bot_essay_state"] = "awaiting_text"
    await send_reply(
        update,
        "Esse matningizni keyingi xabarda yuboring. 50 000 belgigacha qabul qilinadi.\n"
        "Bekor qilish uchun /cancel_essay yuboring.",
    )


async def _handle_bot_essay_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    text = (getattr(update.message, "text", "") or "").strip()
    if not text:
        await send_reply(
            update, "Matnli esse yuboring yoki /cancel_essay bilan bekor qiling."
        )
        return
    await _submit_bot_essay(update, context, text)


async def _submit_bot_essay(
    update: Update, context: ContextTypes.DEFAULT_TYPE, essay_text: str
) -> None:
    """Submit a free-form TEXT essay through the canonical cached grader."""
    from apps.payments.models import SubscriptionUsage

    await _submit_essay_with_quota(
        update,
        context,
        essay_text,
        kind=SubscriptionUsage.Kind.TEXT_ESSAY,
    )


def _update_identity(update, text: str = "") -> str:
    """Stable per-delivery identifier for the essay idempotency key.

    ``update_id`` is the real Telegram value and is always present on a genuine
    update, so production always keys on it. The remaining branches keep a
    repeatable identity for lightweight update doubles / future transports:
    they must never fall back to ``id(update)``, because two *distinct*
    deliveries in one process could then share a key and the second essay would
    silently replay the first reservation instead of being charged.
    """
    update_id = getattr(update, "update_id", None)
    if update_id is not None:
        return str(update_id)
    message = getattr(update, "message", None)
    message_id = getattr(message, "message_id", None)
    if message_id is not None:
        return f"m{message_id}"
    query = getattr(update, "callback_query", None)
    query_id = getattr(query, "id", None)
    if query_id:
        return f"c{query_id}"
    # Last resort: the essay content itself. Distinct essays stay distinct, and
    # a redelivery of the very same essay still replays instead of double
    # charging.
    digest = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    return f"t{digest[:24]}"


async def _submit_essay_with_quota(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    essay_text: str,
    *,
    kind: str,
    idempotency_key: str | None = None,
) -> None:
    """Persist and queue an essay, charging the commercial allowance once.

    The order mirrors the platform-wide essay pipeline: validate → reserve
    quota atomically → create the submission → start grading → commit. The
    reservation is RELEASED when no fresh grading job was delivered (duplicate
    text, provider dispatch failure), so a student is never charged for a
    submission that was not accepted, while an internal AI retry on an already
    queued submission can never be charged twice.
    """
    from apps.essays.models import EssaySubmission
    from apps.essays.services import WordCounter, start_grading
    from apps.essays.views import MAX_ESSAY_LENGTH
    from apps.payments.entitlements import (
        QuotaDenied,
        commit_usage,
        enforce_essay_quota,
        release_usage,
    )
    from apps.payments.models import SubscriptionUsage as _Usage

    kind_label = "rasmli" if kind == _Usage.Kind.IMAGE_ESSAY else "matnli"

    if len(essay_text) > MAX_ESSAY_LENGTH:
        _clear_essay_state(context)
        await send_reply(
            update, f"Esse juda uzun. Maksimal {MAX_ESSAY_LENGTH:,} belgi."
        )
        return
    if not essay_text.strip():
        await send_reply(update, "Esse matni bo'sh bo'lmasligi kerak.")
        return

    user = await _get_or_create_user_async(update)
    if not user:
        _clear_essay_state(context)
        await send_reply(update, "Hisobni aniqlab bo'lmadi. /start ni bosing.")
        return

    # -- Atomic allowance reservation, before anything is persisted ---------
    # The key is derived from the Telegram update identity: Telegram delivers
    # updates at least once with a stable update_id, so a redelivered update
    # replays the existing reservation instead of charging the student twice.
    telegram_id = getattr(update.effective_user, "id", 0)
    key = idempotency_key or (
        f"bot:{kind}:{telegram_id}:{_update_identity(update, essay_text)}"
    )
    try:
        reservation = await _run_db(
            enforce_essay_quota,
            user,
            kind,
            idempotency_key=key,
            source="telegram_bot",
        )
    except QuotaDenied as exc:
        _clear_essay_state(context)
        await send_reply(update, exc.message, reply_markup=_essay_denied_keyboard())
        return

    topic_id = context.user_data.get("bot_essay_topic_id")

    def _create_and_queue():
        topic = None
        if topic_id:
            from apps.essays.models import EssayTopic

            topic = EssayTopic.objects.filter(id=topic_id).first()

        existing = (
            EssaySubmission.objects.filter(
                student=user,
                topic=topic,
                essay_text=essay_text,
                status__in=(
                    EssaySubmission.Status.PENDING,
                    EssaySubmission.Status.GRADED,
                ),
            )
            .order_by("-id")
            .first()
        )
        if existing:
            return existing, None, "existing"

        submission = EssaySubmission.objects.create(
            student=user,
            topic=topic,
            essay_text=essay_text,
            word_count=WordCounter.count(essay_text),
            status=EssaySubmission.Status.DRAFT,
            # Provenance for teacher group reporting (WEB / TELEGRAM / TMA).
            source=EssaySubmission.Source.TELEGRAM,
        )
        result = start_grading(submission, fail_status=EssaySubmission.Status.ERROR)
        return submission, result, "submitted"

    submission, result, state = await _run_db(_create_and_queue)
    _clear_essay_state(context)

    if state == "existing":
        # Nothing new was queued for grading, so the allowance is not spent.
        await _run_db(release_usage, reservation)
        label = (
            "allaqachon qabul qilingan"
            if submission.status == EssaySubmission.Status.PENDING
            else f"allaqachon baholangan: {submission.total_score}/{submission.max_score}"
        )
        await send_reply(
            update,
            f"Bu bir xil {kind_label} esse {label}. Yangi matnni tahrir "
            f"qilsangizgina yangi baho olinadi.",
            reply_markup=_result_keyboard(submission.id),
        )
        return

    if not result or not result.get("success"):
        await _run_db(release_usage, reservation)
        await send_reply(
            update,
            "Baholash navbatga qo'yilmadi: "
            f"{(result or {}).get('error', 'qayta urinib ko‘ring')}.",
        )
        return

    # The grading job was accepted: the allowance is consumed exactly once,
    # even though the AI evaluation itself is still running asynchronously.
    await _run_db(commit_usage, reservation)

    await send_reply(
        update,
        "⏳ *Esse qabul qilindi!*\n\n"
        "Baholash boshlandi (AI tahlili fon rejimida ishlamoqda). Natija tayyor bo'lgach, shu yerga yuboriladi. 🚀",
        parse_mode="Markdown",
        reply_markup=_result_keyboard(submission.id),
    )


async def cancel_essay_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    _clear_essay_state(context)
    await send_reply(update, "Esse topshirish bekor qilindi.")


# ---------------------------------------------------------------------------
# Commercial plans, quotas and Telegram Stars payments
# ---------------------------------------------------------------------------

#: Interactive states for the essay flows (kept in ``context.user_data``).
ESSAY_CHOICE_STATE = "awaiting_choice"
ESSAY_IMAGE_PAGES_STATE = "awaiting_image_pages"
ESSAY_OCR_CONFIRM_STATE = "awaiting_ocr_confirm"
ESSAY_OCR_EDIT_STATE = "awaiting_ocr_text"

_ESSAY_STATE_KEYS = (
    "bot_essay_state",
    "essay_pages",
    "essay_ocr_text",
    "bot_essay_topic_id",
)


def _clear_essay_state(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Drop every key used by the essay flows. True when something was set."""
    cleared = False
    for key in _ESSAY_STATE_KEYS:
        if context.user_data.pop(key, None) is not None:
            cleared = True
    return cleared


def _site_url() -> str:
    from django.conf import settings as _settings

    return getattr(_settings, "SITE_URL", "http://localhost:8000").rstrip("/")


def _result_keyboard(submission_id: int) -> InlineKeyboardMarkup:
    """Link the student to their OWN result page or check status in bot."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📊 Natijani tekshirish",
                    callback_data=f"essay_check:{submission_id}",
                ),
                InlineKeyboardButton(
                    "📄 Web'da ko'rish",
                    url=f"{_site_url()}/essays/result/{submission_id}/",
                ),
            ],
            [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
        ]
    )


def _essay_denied_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💎 Tariflar", callback_data="cb_plans")],
            [
                InlineKeyboardButton(
                    "🌐 Obuna sahifasi", url=f"{_site_url()}/subscribe/"
                )
            ],
        ]
    )


def _pages_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Yana sahifa", callback_data="cb_pages_more")],
            [
                InlineKeyboardButton(
                    "📤 Tekshirishga yuborish", callback_data="cb_pages_done"
                ),
                InlineKeyboardButton(
                    "❌ Bekor qilish", callback_data="cb_pages_cancel"
                ),
            ],
        ]
    )


def _ocr_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data="cb_ocr_confirm")],
            [
                InlineKeyboardButton("✏️ Tahrirlash", callback_data="cb_ocr_edit"),
                InlineKeyboardButton("🔄 Qayta yuborish", callback_data="cb_ocr_retry"),
            ],
        ]
    )


def _plan_quota_line(plan) -> str:
    """Compact Uzbek summary of a plan's essay quota configuration."""

    def bucket(limit, unlimited: bool, noun: str) -> str:
        if unlimited:
            return f"{noun}: cheklanmagan"
        if limit is None:
            return f"{noun}: sozlanmagan"
        return f"{noun}: {limit}/hafta"

    return " · ".join(
        [
            bucket(
                plan.image_essay_weekly_limit, plan.is_unlimited_image_essays, "Rasmli"
            ),
            bucket(
                plan.text_essay_weekly_limit, plan.is_unlimited_text_essays, "Matnli"
            ),
        ]
    )


# ---------------------------------------------------------------------------
# /essay — pick the submission channel
# ---------------------------------------------------------------------------


async def essay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/essay — ask how the student wants to submit the essay."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi. /start ni bosing.")
        return
    _clear_essay_state(context)
    context.user_data["bot_essay_state"] = ESSAY_CHOICE_STATE
    await send_reply(
        update,
        "✍️ *Esse topshirish*\n\nEsenni qanday yuborasiz?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⌨️ Matn orqali", callback_data="cb_essay_text")],
                [InlineKeyboardButton("🖼 Rasm orqali", callback_data="cb_essay_image")],
                [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
            ]
        ),
    )


async def _handle_essay_text_choice(update, context) -> None:
    """Switch to the text-essay flow."""
    context.user_data["bot_essay_state"] = "awaiting_text"
    await send_reply(
        update,
        "Esse matnini keyingi xabarda yuboring (50 000 belgigacha).\n"
        "Bekor qilish uchun /cancel yuboring.",
    )


async def _handle_essay_image_choice(update, context) -> None:
    """Switch to the image-essay flow (page collection)."""
    from django.conf import settings as _settings

    max_pages = int(getattr(_settings, "ESSAY_IMAGE_MAX_PAGES", 10))
    _clear_essay_state(context)
    context.user_data["bot_essay_state"] = ESSAY_IMAGE_PAGES_STATE
    context.user_data["essay_pages"] = []
    await send_reply(
        update,
        "🖼 Esse sahifalarini rasm ko'rinishida yuboring "
        f"(maksimal {max_pages} sahifa).\n\n"
        "Bir nechta sahifani ketma-ket yuborishingiz mumkin. "
        "Tugagach «Tekshirishga yuborish» tugmasini bosing.",
        reply_markup=_pages_keyboard(),
    )


# ---------------------------------------------------------------------------
# Image essays — page collection, OCR and confirmation
# ---------------------------------------------------------------------------


async def essay_image_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Collect essay page images while the image-essay flow is active.

    Registered in a LOWER handler group than the payment-screenshot handler, so
    when this flow is not active it returns immediately and lets that handler
    receive its own photos.
    """
    current_state = context.user_data.get("bot_essay_state")
    if current_state not in (
        ESSAY_IMAGE_PAGES_STATE,
        "awaiting_submission",
        "awaiting_text",
    ):
        return
    message = update.message
    if message is None:
        return

    if current_state in ("awaiting_submission", "awaiting_text"):
        context.user_data["bot_essay_state"] = ESSAY_IMAGE_PAGES_STATE
        context.user_data["essay_pages"] = []

    from django.conf import settings as _settings

    max_pages = int(getattr(_settings, "ESSAY_IMAGE_MAX_PAGES", 10))
    max_bytes = int(getattr(_settings, "ESSAY_IMAGE_MAX_BYTES", 10 * 1024 * 1024))

    file_id = ""
    file_size = 0
    if message.photo:
        largest = message.photo[-1]
        file_id, file_size = largest.file_id, largest.file_size or 0
    elif message.document:
        document = message.document
        if not (document.mime_type or "").lower().startswith("image/"):
            await send_reply(update, "Faqat rasm (JPEG/PNG) yuborishingiz mumkin.")
            return
        file_id, file_size = document.file_id, document.file_size or 0
    if not file_id:
        return

    if file_size and file_size > max_bytes:
        await send_reply(
            update,
            f"Rasm hajmi juda katta ({file_size // 1024} KB). "
            f"Maksimal {max_bytes // (1024 * 1024)} MB.",
            reply_markup=_pages_keyboard(),
        )
        return

    pages = context.user_data.setdefault("essay_pages", [])
    if len(pages) >= max_pages:
        await send_reply(
            update,
            f"Bitta essening maksimal sahifa soni: {max_pages}. "
            "Iltimos, «Tekshirishga yuborish» yoki «Bekor qilish»ni tanlang.",
            reply_markup=_pages_keyboard(),
        )
        return

    # One multi-page essay is ONE image-essay submission, not one per photo.
    pages.append(file_id)
    await send_reply(
        update,
        f"✅ {len(pages)} ta sahifa qabul qilindi.",
        reply_markup=_pages_keyboard(),
    )


async def _handle_pages_more(update, context) -> None:
    """Prompt for the next page without ending the flow."""
    if context.user_data.get("bot_essay_state") != ESSAY_IMAGE_PAGES_STATE:
        await send_reply(update, "Rasm yuborish bosqichi faol emas. /essay ni bosing.")
        return
    count = len(context.user_data.get("essay_pages") or [])
    await send_reply(
        update,
        f"Keyingi sahifani yuboring. Hozir: {count} ta sahifa.",
        reply_markup=_pages_keyboard(),
    )


async def _handle_pages_cancel(update, context) -> None:
    """Abandon the image-essay flow (no quota is consumed)."""
    _clear_essay_state(context)
    await send_reply(
        update,
        "Rasmli esse yuborish bekor qilindi.",
        reply_markup=_main_menu_keyboard(),
    )


async def _handle_pages_done(update, context) -> None:
    """Transcribe the collected pages, then ask the student to confirm."""
    import asyncio

    from apps.essays.ocr import (
        OCRFailed,
        OCRUnavailable,
        OCRValidationError,
        extract_text,
    )

    pages = list(context.user_data.get("essay_pages") or [])
    if not pages:
        await send_reply(
            update,
            "Avval kamida bitta sahifa rasm yuboring.",
            reply_markup=_pages_keyboard(),
        )
        return

    await send_reply(update, "🔍 Rasmlar tahlil qilinmoqda, biroz kuting...")

    # Downloads are I/O and OCR is CPU/HTTP bound, so neither blocks the loop.
    try:
        raw_pages = []
        for file_id in pages:
            telegram_file = await context.bot.get_file(file_id)
            raw_pages.append(bytes(await telegram_file.download_as_bytearray()))
        result = await asyncio.to_thread(extract_text, raw_pages)
    except OCRUnavailable as exc:
        # No OCR provider configured: never fabricate text, never charge quota.
        await send_reply(update, str(exc), reply_markup=_pages_keyboard())
        return
    except OCRValidationError as exc:
        await send_reply(
            update,
            f"Rasm qabul qilinmadi: {exc}",
            reply_markup=_pages_keyboard(),
        )
        return
    except OCRFailed as exc:
        await send_reply(
            update,
            f"{exc}\nQayta urinib ko'ring yoki esseni matn ko'rinishida yuboring (/essay).",
            reply_markup=_pages_keyboard(),
        )
        return
    except Exception:
        logger.exception(
            "Unexpected OCR failure for chat=%s",
            getattr(update.effective_chat, "id", None),
        )
        await send_reply(
            update,
            "Rasmdan matn ajratishda kutilmagan xatolik. Keyinroq urinib ko'ring.",
            reply_markup=_pages_keyboard(),
        )
        return

    preview = result.text if len(result.text) <= 1200 else result.text[:1200] + "\n…"
    warning = ""
    if result.is_probably_incomplete:
        warning = (
            "\n⚠️ Rasmdan juda kam matn aniqlandi. Iltimos, matnni tekshirib, "
            "kerak bo'lsa tahrirlang.\n"
        )
    context.user_data["essay_ocr_text"] = result.text
    context.user_data["bot_essay_state"] = ESSAY_OCR_CONFIRM_STATE
    await send_reply(
        update,
        "Rasmdan quyidagi matn aniqlandi:\n\n"
        f"{preview}\n"
        f"{warning}\n"
        "Tasdiqlasangiz, esse baholashga yuboriladi.",
        reply_markup=_ocr_confirm_keyboard(),
    )


async def _handle_ocr_confirm(update, context) -> None:
    """Grade the CONFIRMED OCR text as one image essay."""
    from apps.payments.models import SubscriptionUsage

    text = (context.user_data.get("essay_ocr_text") or "").strip()
    if not text:
        await send_reply(update, "Matn topilmadi. /essay bilan qaytadan boshlang.")
        return
    await _submit_essay_with_quota(
        update,
        context,
        text,
        kind=SubscriptionUsage.Kind.IMAGE_ESSAY,
    )


async def _handle_ocr_edit(update, context) -> None:
    """Ask for a corrected transcription before grading."""
    context.user_data["bot_essay_state"] = ESSAY_OCR_EDIT_STATE
    await send_reply(
        update,
        "Tuzatilgan esse matnini keyingi xabarda yuboring. "
        "/cancel bilan bekor qilish mumkin.",
    )


async def _handle_ocr_retry(update, context) -> None:
    """Discard the pages and start the image flow over."""
    from django.conf import settings as _settings

    max_pages = int(getattr(_settings, "ESSAY_IMAGE_MAX_PAGES", 10))
    _clear_essay_state(context)
    context.user_data["bot_essay_state"] = ESSAY_IMAGE_PAGES_STATE
    context.user_data["essay_pages"] = []
    await send_reply(
        update,
        f"🖼 Sahifalarni qaytadan yuboring (maksimal {max_pages} sahifa).",
        reply_markup=_pages_keyboard(),
    )


async def _handle_ocr_corrected_text(update, context) -> None:
    """Text state handler for a manually corrected OCR transcription."""
    from apps.payments.models import SubscriptionUsage

    text = (getattr(update.message, "text", "") or "").strip()
    if not text:
        await send_reply(
            update,
            "Matn bo'sh. Iltimos, esse matnini yuboring yoki /cancel ni bosing.",
        )
        return
    await _submit_essay_with_quota(
        update,
        context,
        text,
        kind=SubscriptionUsage.Kind.IMAGE_ESSAY,
    )


# ---------------------------------------------------------------------------
# /plans, card payments & receipt uploads
# ---------------------------------------------------------------------------


async def plans_and_payment_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show Grand Education card details, plans and payment receipt instructions."""
    from django.conf import settings as _settings

    card_number = getattr(_settings, "PAYMENT_CARD_NUMBER", "") or "9860 **** **** ****"
    card_holder = getattr(_settings, "PAYMENT_CARD_HOLDER", "") or "KOMILJON R"
    starter_price = getattr(_settings, "PLAN_STARTER_PRICE", 0) or 15000
    pro_price = getattr(_settings, "PLAN_PRO_PRICE", 0) or 49000
    premium_price = getattr(_settings, "PLAN_PREMIUM_PRICE", 0) or 60000

    text = (
        f"💎 *GRAND EDUCATION TARIF VA OBUNA REJALARI*\n\n"
        f"1️⃣ *⚡️ Starter tarifi — {starter_price:,} so'm / 30 kun*\n"
        f"• 5 ta AI rasmli / 3 ta matn esse (haftasiga)\n"
        f"• Standart testlar\n"
        f"• Kunlik 20 ta AI repetitor so'rovi\n\n"
        f"2️⃣ *🚀 Pro tarifi — {pro_price:,} so'm / 30 kun (Tavsiya etiladi)*\n"
        f"• Haftalik 15 ta esse baholash\n"
        f"• Barcha CBT va Mock testlar\n"
        f"• Kunlik 50 ta AI repetitor so'rovi\n\n"
        f"3️⃣ *👑 Premium tarifi — {premium_price:,} so'm / 30 kun*\n"
        f"• ✍️ Cheksiz esse baholash (12 mezon + AI tahriri)\n"
        f"• 📚 Barcha Mock testlar va Fast CBT\n"
        f"• 🧠 Cheksiz 24/7 AI repetitor\n"
        f"• 📜 PDF Sertifikatlar va ustoz tekshiruvi\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 *KARTA ORQALI TO'LOV:*\n"
        f"Karta raqami: `{card_number}`\n"
        f"Karta egasi: *{card_holder}*\n\n"
        f"📲 *TO'LOVNI FAOLLASHTIRISH:*\n"
        f"1. Quyidagi tugmalar orqali kerakli tarifni tanlang.\n"
        f"2. To'lov chekini (screenshot/kvitansiya) to'g'ridan-to'g'ri shu chatga *rasm* qilib yuboring.\n"
        f"3. Chek kelgach, 5-15 daqiqa ichida admin tekshiradi va obunangiz faollashadi!"
    )

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"⚡️ Starter ({starter_price:,} so'm)",
                    callback_data="pay_plan_starter",
                ),
                InlineKeyboardButton(
                    f"🚀 Pro ({pro_price:,} so'm)", callback_data="pay_plan_pro"
                ),
            ],
            [
                InlineKeyboardButton(
                    f"👑 Premium ({premium_price:,} so'm)",
                    callback_data="pay_plan_premium",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🌐 Veb-saytda to'lash", url="https://grandec.uz/subscribe/"
                ),
                InlineKeyboardButton("📊 Mening limitlarim", callback_data="cb_limits"),
            ],
            [
                InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main"),
            ],
        ]
    )
    await send_reply(update, text, parse_mode="Markdown", reply_markup=buttons)


async def plans_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/plans — list purchasable plans with their Telegram Stars prices."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi. /start ni bosing.")
        return

    def _load():
        from apps.payments.models import SubscriptionPlan

        return list(
            SubscriptionPlan.objects.filter(is_active=True, is_public=True)
            .exclude(plan_type=SubscriptionPlan.PlanType.TEACHER_SPONSORED)
            .order_by("sort_order", "price_monthly")
        )

    plans = await _run_db(_load)
    if not plans:
        await send_reply(
            update, "Hozircha tariflar mavjud emas. Keyinroq urinib ko'ring."
        )
        return

    lines = ["💎 *Grandec tariflari*", ""]
    buttons = []
    for plan in plans:
        price = int(plan.price_monthly or 0)
        lines.append(f"📦 *{plan.name}* — {price:,} so'm / {plan.duration_days} kun")
        lines.append(f"   {_plan_quota_line(plan)}")
        stars_price = plan.telegram_stars_price
        if stars_price:
            lines.append(f"   💫 Narx: *{stars_price} Stars*")
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"💫 {plan.name} — {stars_price} Stars",
                        callback_data=f"tg_buy_{plan.id}",
                    )
                ]
            )
        else:
            lines.append(
                "   ⚠️ Telegram orqali sotuv sozlanmagan "
                "(administrator Stars narxini kiritishi kerak)."
            )
        lines.append("")

    lines.append("To'lov *Telegram Stars* orqali amalga oshiriladi.")
    buttons.append([InlineKeyboardButton("📊 Limitlarim", callback_data="cb_limits")])
    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")])
    await send_reply(
        update,
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/buy [start|pro|plan_id] — start a Telegram Stars purchase."""
    from apps.payments.models import SubscriptionPlan

    args = [a for a in (context.args or []) if a]
    if not args:
        await plans_handler(update, context)
        return

    token = args[0].strip().lower()

    def _resolve():
        queryset = SubscriptionPlan.objects.filter(is_active=True, is_public=True)
        if token.isdigit():
            return queryset.filter(id=int(token)).first()
        return queryset.filter(plan_type=token).first()

    plan = await _run_db(_resolve)
    if plan is None:
        await send_reply(update, "Reja topilmadi. /plans ni bosing.")
        return
    await _send_stars_invoice(update, context, plan)


async def _tg_buy_callback(update, context, plan_id: int) -> None:
    """Handle a tg_buy_<plan_id> button — send the Stars invoice."""
    from apps.payments.models import SubscriptionPlan

    plan = await _run_db(
        lambda: SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()
    )
    if plan is None:
        await send_reply(update, "Reja topilmadi.")
        return
    await _send_stars_invoice(update, context, plan)


async def _send_stars_invoice(update, context, plan) -> None:
    """Create an internal order and hand Telegram a Stars invoice for it."""
    from telegram import LabeledPrice

    from apps.payments import stars

    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi. /start ni bosing.")
        return

    try:
        order = await _run_db(stars.create_order, user, plan)
    except ValueError as exc:
        # e.g. no Stars price configured yet, or the plan is not sellable.
        await send_reply(update, f"❌ {exc}")
        return

    chat_id = getattr(update.effective_chat, "id", None) or update.effective_user.id
    try:
        await context.bot.send_invoice(
            chat_id=chat_id,
            title=f"Grandec {plan.name}",
            description=(plan.description or f"Grandec {plan.name} obuna")[:255],
            payload=order.payload,
            provider_token="",  # Telegram Stars requires an empty token
            currency=stars.STARS_CURRENCY,
            prices=[
                LabeledPrice(
                    label=f"Grandec {plan.name}",
                    amount=order.amount_stars,
                )
            ],
        )
    except Exception:
        logger.exception("Failed to send Stars invoice for order %s", order.payload)
        await _run_db(stars.cancel_order, order)
        await send_reply(
            update,
            "To'lov hisob-fakturasini yuborib bo'lmadi. Keyinroq urinib ko'ring "
            "yoki /paysupport orqali bog'laning.",
        )
        return

    await _run_db(stars.mark_invoice_sent, order)


async def pre_checkout_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Answer a Telegram Stars pre-checkout query. Never activates access."""
    from apps.payments import stars

    query = update.pre_checkout_query
    if query is None:
        return
    ok, error, _order = await _run_db(
        stars.validate_pre_checkout,
        payload=query.invoice_payload,
        currency=query.currency,
        total_amount=query.total_amount,
    )
    try:
        if ok:
            await query.answer(ok=True)
        else:
            await query.answer(
                ok=False,
                error_message=(error or "To'lovni tasdiqlab bo'lmadi.")[:200],
            )
    except Exception:
        logger.exception(
            "pre_checkout answer failed for payload=%s",
            query.invoice_payload,
        )


def _payment_summary(subscription) -> dict:
    """Read the paid subscription's plan name safely (inside the sync layer)."""
    if subscription is None:
        return {}
    plan = subscription.plan
    return {
        "plan_name": plan.name if plan else "",
        "expires_at": (
            subscription.expires_at.strftime("%d.%m.%Y")
            if subscription.expires_at
            else ""
        ),
    }


async def successful_payment_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Activate a subscription from a verified Telegram Stars payment."""
    from apps.payments import stars

    message = update.message
    payment = getattr(message, "successful_payment", None) if message else None
    if payment is None:
        return

    user = await _get_or_create_user_async(update)
    if not user:
        logger.warning(
            "successful_payment for an unresolvable user (payload=%s)",
            payment.invoice_payload,
        )
        return

    ok, text, subscription = await _run_db(
        stars.activate_from_successful_payment,
        payload=payment.invoice_payload,
        currency=payment.currency,
        total_amount=payment.total_amount,
        telegram_payment_charge_id=payment.telegram_payment_charge_id,
        provider_payment_charge_id=payment.provider_payment_charge_id or "",
        raw={
            "invoice_payload": payment.invoice_payload,
            "currency": payment.currency,
            "total_amount": payment.total_amount,
        },
    )

    if not ok:
        await send_reply(update, f"❌ {text}\nYordam uchun /paysupport ni bosing.")
        return

    summary = await _run_db(_payment_summary, subscription)
    lines = [f"✅ {text}"]
    if summary.get("plan_name"):
        lines.append(f"📦 Reja: *{summary['plan_name']}*")
    if summary.get("expires_at"):
        lines.append(f"⏰ Amal qiladi: {summary['expires_at']}")
    lines.append("")
    lines.append("Limitlaringizni /limits buyrug'i orqali ko'rishingiz mumkin.")
    await send_reply(
        update,
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=_main_menu_keyboard(),
    )


# ---------------------------------------------------------------------------
# /myplan, /limits, /paysupport, /cancel
# ---------------------------------------------------------------------------

_SOURCE_LABELS = {
    "override": "Admin kvota ustunligi",
    "sponsored": "Ustoz guruhi (homiylik)",
    "subscription": "To'langan obuna",
    "default": "Bepul / standart",
}


async def myplan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/myplan — show the effective plan and entitlement card."""
    from django.utils import timezone

    from apps.payments.entitlements import get_effective_entitlement

    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi. /start ni bosing.")
        return

    def _load():
        entitlement = get_effective_entitlement(user)
        return {
            "source": entitlement.source,
            "plan_name": entitlement.plan_name,
            "is_sponsored": entitlement.is_sponsored,
            "expires_at": entitlement.expires_at,
        }

    data = await _run_db(_load)

    expires_str = "Cheksiz"
    if data["expires_at"]:
        days = max(0, (data["expires_at"] - timezone.now()).days)
        expires_str = f"{data['expires_at']:%d.%m.%Y} ({days} kun qoldi)"

    status_icon = "🎁" if data["is_sponsored"] else "💎"
    source_label = _SOURCE_LABELS.get(data["source"], data["source"])

    card = (
        f"💳 *TARIF REJASI KARTASI*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Foydalanuvchi: *{user.get_full_name() or user.username}*\n"
        f"{status_icon} Joriy tarif: *{data['plan_name']}*\n"
        f"🔖 Manba: *{source_label}*\n"
        f"⏳ Amal qilish muddati: *{expires_str}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    if data["is_sponsored"]:
        card += (
            "🎁 *Ustoz homiyligi:* Ushbu tarif ustozingiz tomonidan taqdim etilgan.\n\n"
        )
    else:
        card += "💡 *Qo'shimcha imkoniyatlar uchun tarifni yangilashingiz mumkin.*\n\n"

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📊 Limitlarim", callback_data="cb_limits"),
                InlineKeyboardButton("💎 Tariflar", callback_data="cb_plans"),
            ],
            [
                InlineKeyboardButton("💳 Kurs to'lovlari", callback_data="cb_tuition"),
                InlineKeyboardButton("📅 Davomat", callback_data="cb_attendance"),
            ],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
        ]
    )
    await send_reply(update, card, parse_mode="Markdown", reply_markup=keyboard)


async def mytuition_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/mytuition — private tuition overview card for a student or verified parent."""
    from apps.tuition.services import (
        children_tuition_overview,
        student_tuition_overview,
    )

    if not await _require_private_chat(update):
        return

    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Hisobni aniqlab bo'lmadi. /start ni bosing.")
        return

    def _overview():
        if user.role == "parent":
            children = children_tuition_overview(user)
            return [{**child, "is_child": True} for child in children]
        if user.role == "student":
            return [{**student_tuition_overview(user, limit=8), "is_child": False}]
        return []

    rows = await _run_db(_overview)
    if not rows:
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💎 Tarif rejasi", callback_data="cb_myplan")],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
            ]
        )
        await send_reply(
            update,
            "💳 *KURS TO'LOVLARI*\n━━━━━━━━━━━━━━━━━━━━━━━━━\nSiz uchun ko'rish mumkin bo'lgan kurs to'lovi topilmadi.",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return

    lines = [
        "💳 *KURS TO'LOVLARI KARTASI*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for row in rows:
        name = row.get("student_name", "")
        if row["is_child"]:
            lines.append(f"👤 O'quvchi: *{name}*")

        paid = _format_uzs(row.get("confirmed_paid_uzs", 0))
        debt = _format_uzs(row.get("outstanding_uzs", 0))
        debt_icon = "⚠️" if (row.get("outstanding_uzs", 0) > 0) else "✅"

        lines.append(f"✅ To'langan: *{paid} so'm*")
        lines.append(f"{debt_icon} Qoldiq qarz: *{debt} so'm*")
        lines.append("─────────────────────────")

        invoices = row.get("invoices", [])
        if invoices:
            lines.append("📋 *Hisob-fakturalar:*")
            for inv in invoices[:5]:
                status_emoji = "🟢" if inv.get("status") == "paid" else "🟡"
                lines.append(
                    f"  {status_emoji} *{inv['period_label']}*: {inv['status_label']} "
                    f"(qoldiq: {_format_uzs(inv['balance_uzs'])} so'm)"
                )
        lines.append("")

    lines.append("📌 _Eslatma: Platforma tarifi va kurs to'lovi alohida to'lanadi._")

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🧾 Dalil yuborish", callback_data="payment_proof")],
            [
                InlineKeyboardButton("💎 Platforma tarifi", callback_data="cb_myplan"),
                InlineKeyboardButton("📅 Davomat", callback_data="cb_attendance"),
            ],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
        ]
    )
    await send_reply(
        update, "\n".join(lines), parse_mode="Markdown", reply_markup=keyboard
    )


async def course_payment_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/course_payment — private own/open invoice status; parents use /mytuition."""
    from apps.tuition.models import CourseInvoice

    if not await _require_private_chat(update):
        return

    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Hisobni aniqlab bo'lmadi. /start ni bosing.")
        return
    if user.role != "student":
        await send_reply(
            update, "Bu buyruq faqat o'quvchining shaxsiy hisoblari uchun."
        )
        return

    def _load():
        return list(
            CourseInvoice.objects.filter(student_id=user.pk)
            .select_related(
                "policy",
                "course",
            )
            .order_by("-billing_period_start", "-pk")[:12]
        )

    invoices = await _run_db(_load)
    if not invoices:
        await send_reply(update, "Siz uchun kurs hisob-fakturasi mavjud emas.")
        return
    lines = ["💳 *Kurs to'lovlari*", ""]
    for invoice in invoices:
        lines.append(
            f"• {invoice.period_label}: {invoice.status_label} · "
            f"qoldiq {_format_uzs(invoice.balance_uzs)} so'm"
            + (" (to'lov tasdig'i kutilmoqda)" if invoice.awaiting_confirmation else "")
        )
    await send_reply(update, "\n".join(lines), parse_mode="Markdown")


async def payment_history_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/payment_history — this linked user's private course-payment history."""
    from apps.tuition.models import CoursePayment

    if not await _require_private_chat(update):
        return

    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Hisobni aniqlab bo'lmadi. /start ni bosing.")
        return

    def _load():
        if user.role == "parent":
            from apps.accounts.models import ParentStudentLink

            child_ids = ParentStudentLink.objects.filter(
                parent=user,
                is_approved=True,
                student__is_active=True,
            ).values_list("student_id", flat=True)
            return list(
                CoursePayment.objects.filter(student_id__in=child_ids)
                .select_related(
                    "invoice",
                    "student",
                )
                .order_by("-created_at")[:20]
            )
        if user.role != "student":
            return []
        return list(
            CoursePayment.objects.filter(student_id=user.pk)
            .select_related(
                "invoice",
            )
            .order_by("-created_at")[:20]
        )

    payments = await _run_db(_load)
    if not payments:
        await send_reply(update, "To'lovlar tarixi bo'sh.")
        return
    lines = ["🧾 *Kurs to'lovlari tarixi*", ""]
    for payment in payments:
        period = (
            payment.invoice.period_label
            if payment.invoice_id
            else "Hisobga biriktirilmagan"
        )
        student_name = (
            f"{payment.student.get_full_name() or payment.student.email} · "
            if user.role == "parent"
            else ""
        )
        lines.append(
            f"• {student_name}{period}: {_format_uzs(payment.amount_uzs)} so'm · "
            f"{payment.get_status_display()}"
        )
    await send_reply(update, "\n".join(lines), parse_mode="Markdown")


async def payment_proof_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/payment_proof <invoice_id> <amount> [reference] records a private claim."""
    if not await _require_private_chat(update):
        return

    from apps.tuition.models import CourseInvoice, PaymentMethod
    from django.db import IntegrityError
    from apps.tuition import services as tuition_services

    user = await _get_or_create_user_async(update)
    if not user or user.role not in ("student", "parent"):
        await send_reply(
            update,
            "Hisobni aniqlab bo'lmadi yoki buyruq faqat o'quvchi va tasdiqlangan ota-onalar uchun.",
        )
        return
    args = [value.strip() for value in (context.args or [])]
    if len(args) < 2:
        await send_reply(
            update, "Format: /payment_proof <hisob_id> <summa> [to'lov_raqami]"
        )
        return
    try:
        invoice_id = int(args[0])
        amount = Decimal(args[1].replace(",", "."))
        reference = " ".join(args[2:])[:120]
        if amount <= 0:
            raise ValueError
    except (ValueError, InvalidOperation):
        await send_reply(update, "Hisob raqami yoki summa noto'g'ri.")
        return

    def _submit():
        from apps.accounts.models import ParentStudentLink

        student_id = user.pk
        if user.role == "parent":
            student_id = (
                ParentStudentLink.objects.filter(
                    parent=user,
                    is_approved=True,
                    student__is_active=True,
                )
                .values_list("student_id", flat=True)
                .first()
            )
            if student_id is None:
                return None, "Tasdiqlangan farzand hisobiga to'lov bog'lanmadi."
        invoice = (
            CourseInvoice.objects.filter(pk=invoice_id, student_id=student_id)
            .select_related(
                "policy",
                "student",
            )
            .first()
        )
        if invoice is None:
            return None, "Hisob-faktura topilmadi."
        try:
            payment = tuition_services.register_payment(
                student=invoice.student,
                invoice=invoice,
                amount=amount,
                method=PaymentMethod.CARD,
                reference=reference,
                submitted_by=user,
            )
        except tuition_services.TuitionError as exc:
            return None, str(exc)
        return payment, None

    try:
        payment, error = await _run_db(_submit)
    except IntegrityError:
        await send_reply(update, "Bu to'lov raqami avval yuborilgan.")
        return
    if error:
        await send_reply(update, f"To'lov dalilini qabul qilib bo'lmadi: {error}")
        return
    await send_reply(
        update,
        f"✅ {payment.pk}-raqamli to'lov da'vosi qabul qilindi, tasdiqlash kutilmoqda. "
        "Bu tasdiqlanmaguncha to'lov hisoblanmaydi.",
    )


@require_role("TEACHER")
async def weekly_report_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/weekly_report [group_id] [history] — authorized private teacher reports."""
    if not await _require_private_chat(update):
        return

    from apps.attendance.services import teacher_groups
    from apps.weekly_reports import delivery as report_delivery
    from apps.weekly_reports.models import WeeklyGroupReport

    user = await _get_or_create_user_async(update)
    if not user or not await _run_db(_is_teacher_account, user):
        await send_reply(
            update, "Bu buyruq faqat o'qituvchilar va administratorlar uchun."
        )
        return
    args = [value.strip() for value in (context.args or [])]
    group_id = None
    if args and args[0].isdigit():
        group_id = int(args.pop(0))
    include_history = bool(args and args[0].lower() in ("history", "tarix"))
    can_view_history = is_platform_admin(user) or await _run_db(
        user.has_perm,
        "weekly_reports.view_weeklygroupreport",
    )
    include_history = include_history and can_view_history

    def _load():
        groups = teacher_groups(user)
        qs = WeeklyGroupReport.objects.filter(group__in=groups).select_related("group")
        if group_id:
            qs = qs.filter(group_id=group_id)
        if not include_history:
            qs = qs.filter(is_current=True)
        return list(qs.order_by("-period_start", "-version")[:20])

    reports = await _run_db(_load)
    if not reports:
        await send_reply(update, "Sizga tegishli haftalik hisobot topilmadi.")
        return
    lines = ["📊 *Haftalik hisobotlar*", ""]
    for report in reports:
        summary = await _run_db(report_delivery.visible_summary, report, user)
        attendance = summary.get("attendance", {})
        essays = summary.get("essays", {})
        tests = summary.get("tests", {})
        lines.append(
            f"*{report.group.name} · {report.period_label} (v{report.version})*\n"
            f"Davomat: {attendance.get('attendance_percentage', '—')}% · "
            f"Kechikdi: {attendance.get('late', 0)} · "
            f"Sababsiz yo'qlik: {attendance.get('unexcused_absences', 0)}\n"
            f"Esse: {essays.get('graded', 0)} baholangan / {essays.get('pending_ai', 0)} kutilmoqda · "
            f"Test: {tests.get('completed_attempts', 0)} yakunlangan"
        )
        finance = summary.get("finance")
        if finance:
            lines.append(
                f"Moliya jami qoldiq: {_format_uzs(finance.get('outstanding_uzs', 0))} so'm"
            )
    await send_reply(update, "\n".join(lines)[:4000], parse_mode="Markdown")


@require_role("TEACHER")
async def group_payments_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/group_payments <group_id> — aggregate-only for explicit finance readers."""
    if not await _require_private_chat(update):
        return

    from apps.accounts.access import is_platform_admin
    from apps.tuition import services as tuition_services
    from apps.tuition.permissions import can_view_tuition
    from apps.courses.models import StudentGroup

    user = await _get_or_create_user_async(update)
    if not user or not await _run_db(_is_teacher_account, user):
        await send_reply(update, "Bu buyruq faqat vakolatli xodimlar uchun.")
        return
    if not can_view_tuition(user):
        await send_reply(
            update, "To'lovlarni ko'rish uchun alohida moliyaviy ruxsat kerak."
        )
        return
    args = [value.strip() for value in (context.args or [])]
    if len(args) != 1 or not args[0].isdigit():
        await send_reply(update, "Format: /group_payments <guruh_id>")
        return

    def _load():
        groups = StudentGroup.objects.filter(pk=int(args[0]))
        if not is_platform_admin(user):
            groups = groups.filter(teacher=user)
        group = groups.first()
        if group is None:
            return None, None
        period_start, period_end = tuition_services.month_bounds(
            tuition_services.today()
        )
        return group, tuition_services.group_finance_summary(
            group, period_start, period_end
        )

    group, summary = await _run_db(_load)
    if group is None:
        await send_reply(update, "Guruh topilmadi.")
        return
    await send_reply(
        update,
        f"💳 *{group.name} — umumiy to'lovlar*\n"
        f"To'langan: {summary.get('paid_count', 0)} · "
        f"To'lanmagan: {summary.get('unpaid_count', 0)} · "
        f"Qoldiq: {_format_uzs(summary.get('outstanding_uzs', 0))} so'm",
        parse_mode="Markdown",
    )


def _format_uzs(value) -> str:
    return f"{int(value or 0):,}".replace(",", " ")


async def limits_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/limits — server-calculated remaining allowances and cooldown."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.payments.entitlements import (
        cooldown_seconds_remaining,
        format_duration,
        get_remaining_limits,
    )

    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi. /start ni bosing.")
        return

    data = await _run_db(get_remaining_limits, user)
    cooldown = await _run_db(cooldown_seconds_remaining, user)

    def bucket_line(key: str, label: str) -> str:
        bucket = data[key]
        if bucket["unlimited"]:
            return f"• {label}: Cheklanmagan"
        if bucket["limit"] is None:
            return f"• {label}: administrator sozlamagan"
        return f"• {label}: {bucket['remaining']}/{bucket['limit']} qoldi"

    lines = [f"📊 *Limitlaringiz* — {data['plan_name']}", ""]
    lines.append(bucket_line("image_essay", "Rasmli esse"))
    lines.append(bucket_line("text_essay", "Matnli esse"))
    lines.append(bucket_line("test", "Testlar"))

    if cooldown > 0:
        until = timezone.localtime(timezone.now() + timedelta(seconds=cooldown))
        lines.append("")
        lines.append(
            f"⏳ Keyingi matnli esse: *{until:%H:%M}* "
            f"({format_duration(cooldown)}dan keyin)"
        )

    lines.append("")
    lines.append(
        f"🔄 Davr: {str(data['period_start'])[:10]} — {str(data['period_end'])[:10]}"
    )
    lines.append("")
    lines.append("Barcha raqamlar serverda hisoblanadi.")
    await send_reply(
        update,
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💎 Tariflar", callback_data="cb_plans")],
                [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
            ]
        ),
    )


async def paysupport_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/paysupport — payment support information."""
    from django.conf import settings as _settings

    admin_username = getattr(_settings, "PAYMENT_ADMIN_USERNAME", "")
    lines = [
        "🆘 *To'lov bo'yicha yordam*",
        "",
        "• Bot ichidagi xaridlar *Telegram Stars* (XTR) orqali amalga "
        "oshiriladi — summa Telegram hisobingizdan yechiladi.",
        "• To'lov tasdiqlangach obuna avtomatik faollashadi.",
        "• To'lovlar tarixini Telegram → Sozlamalar → To'lovlar "
        "bo'limidan ko'rishingiz mumkin.",
        "• Xato yechilgan to'lov yoki obuna bo'yicha savollar uchun "
        "biz bilan bog'laning.",
    ]
    if admin_username:
        lines.append(f"👤 Administrator: @{admin_username.lstrip('@')}")
    lines.append(f"🌐 Obuna sahifasi: {_site_url()}/subscribe/")
    lines.append("")
    lines.append("Murojaatda to'lov vaqti va summasini yozib yuboring.")
    await send_reply(update, "\n".join(lines), parse_mode="Markdown")


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cancel — safely abandon whatever interactive flow is in progress."""
    cleared = []
    if _clear_essay_state(context):
        cleared.append("esse yuborish")
    if context.user_data.pop("payment_state", None):
        cleared.append("to'lov")
    context.user_data.pop("selected_plan_id", None)
    if context.user_data.get("auth_state"):
        _clear_auth_state(context)
        cleared.append("kirish")

    if cleared:
        await send_reply(
            update,
            "✅ Bekor qilindi: " + ", ".join(cleared) + ".",
            reply_markup=_main_menu_keyboard(),
        )
    else:
        await send_reply(
            update,
            "Bekor qilinadigan amal yo'q.",
            reply_markup=_main_menu_keyboard(),
        )


# ---------------------------------------------------------------------------
# /essays
# ---------------------------------------------------------------------------


async def essays_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /essays or '✍️ Esse yozish' — show topics with inline buttons."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    from apps.essays.models import EssayTopic, EssaySubmission

    def _get_essay_data():
        topics = list(
            EssayTopic.objects.filter(is_active=True).order_by("-created_at")[:10]
        )
        user_subs = {
            s.topic_id: s for s in EssaySubmission.objects.filter(student=user)
        }
        return topics, user_subs

    topics, user_subs = await _run_db(_get_essay_data)

    if not topics:
        await send_reply(
            update,
            "✍️ *Esse yozish*\n\n"
            "Hozircha tizimda tayyor mavzular mavjud emas. Biroq siz erkin mavzuda esse yozishingiz mumkin:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📝 Erkin mavzuda yozish", callback_data="cb_topic_select:0"
                        )
                    ],
                    [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
                ]
            ),
        )
        return

    text = "✍️ *Esse yozish*\n\nMavzuni tanlang yoki erkin mavzuda yozing 👇\n\n"
    buttons = []

    for i, topic in enumerate(topics, 1):
        lock = "🔒" if topic.password else "📝"
        sub = user_subs.get(topic.id)
        if sub:
            if sub.status == "graded":
                status = (
                    f"✅ {sub.total_score}/{sub.max_score}"
                    if sub.total_score
                    else "✅ Baholangan"
                )
            else:
                status = f"⏳ {sub.get_status_display()}"
        else:
            status = "🆕 Yangi"

        text += (
            f"{i}. {lock} *{topic.title}*\n"
            f"   📏 {topic.word_limit_min}-{topic.word_limit_max} so'z · ⏱ {topic.time_limit_minutes} daqiqa\n"
            f"   📌 Holat: {status}\n\n"
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    f"✍️ {topic.title[:32]}",
                    callback_data=f"cb_topic_select:{topic.id}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "📝 Erkin mavzu (Mavzusiz yozish)", callback_data="cb_topic_select:0"
            )
        ]
    )
    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")])

    await send_reply(
        update,
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def essay_topic_select_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, topic_id: int
) -> None:
    """Set active topic and prompt user to submit text or photo."""
    query = update.callback_query
    if query:
        try:
            await query.answer()
        except Exception:
            pass

    context.user_data["bot_essay_state"] = "awaiting_submission"
    context.user_data["bot_essay_topic_id"] = topic_id if topic_id > 0 else None

    title = "Erkin mavzu (Mavzusiz)"
    desc = ""
    limits_line = ""

    if topic_id > 0:
        from apps.essays.models import EssayTopic

        topic = await _run_db(lambda: EssayTopic.objects.filter(id=topic_id).first())
        if topic:
            title = topic.title
            if topic.description:
                desc = f"\n💬 _{topic.description}_\n"
            t_min = (
                f"⏱ {topic.time_limit_minutes} daqiqa"
                if topic.time_limit_minutes
                else ""
            )
            w_lim = f"📏 {topic.word_limit_min}-{topic.word_limit_max} so'z"
            limits_line = f"\n{t_min} · {w_lim}\n"

    text = (
        f"✍️ *Esse yozish*\n\n"
        f"📚 Mavzu: *{title}*{desc}{limits_line}\n"
        f"Endi essangizni yuborishingiz mumkin:\n"
        f"1️⃣ *Matn yuborish:* Esse matnini shu yerga yozing yoki nusxalab yuboring ⌨️\n"
        f"2️⃣ *Rasm yuborish:* Daftaringiz sahifasini rasm holatida yuboring 📸\n\n"
        f"_Jarayonni to'xtatish uchun quyidagi tugmani bosing:_"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_essay")],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
        ]
    )

    await send_reply(update, text, parse_mode="Markdown", reply_markup=keyboard)


async def essay_improve_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, submission_id: int
) -> None:
    """Improve essay via AI and return the upgraded version directly in chat."""
    query = update.callback_query
    user = await _get_or_create_user_async(update)
    if not user:
        if query:
            await query.answer("Foydalanuvchi aniqlanmadi")
        return

    if query:
        try:
            await query.answer("🪄 AI orqali takomillashtirilmoqda...")
        except Exception:
            pass

    from apps.essays.models import EssaySubmission
    from apps.essays.services import generate_improved_essay

    def _check_cached_or_consume():
        sub = EssaySubmission.objects.filter(id=submission_id, student=user).first()
        if not sub:
            return False, "Esse topilmadi."
        if sub.improved_content:
            return True, ""
        from apps.payments.ai_quota import check_and_consume_ai_quota

        return check_and_consume_ai_quota(user)

    allowed, _ = await _run_db(_check_cached_or_consume)
    if not allowed:
        msg = (
            "⚠️ *Sizning bugungi AI limitingiz tugadi!*\n\n"
            "Cheksiz AI tahlili va barcha imkoniyatlar uchun tarifingizni yangilang."
        )
        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "💳 Tarifni yangilash", callback_data="cb_plans"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Natijaga qaytish",
                        callback_data=f"essay_check:{submission_id}",
                    )
                ],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
            ]
        )
        await send_reply(update, msg, parse_mode="Markdown", reply_markup=buttons)
        return

    def _improve():
        sub = EssaySubmission.objects.filter(id=submission_id, student=user).first()
        if not sub:
            return None, None, "Esse topilmadi."
        try:
            content = generate_improved_essay(sub)
            orig_text = getattr(sub, "essay_text", "") or ""
            return content, orig_text, None
        except Exception as exc:
            return None, None, str(exc)

    content, orig_text, err = await _run_db(_improve)
    if err or not content:
        msg = f"❌ Esseni qayta yozishda xatolik yuz berdi: {err or 'Noma`lum xatolik'}\n\nIltimos, qaytadan urinib ko'ring."
        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔙 Natijaga qaytish",
                        callback_data=f"essay_check:{submission_id}",
                    )
                ],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
            ]
        )
        await send_reply(update, msg, reply_markup=buttons)
        return

    preview = content[:3200]
    orig_snippet = (orig_text or "")[:400]
    orig_section = (
        f"📝 *Asl matn (parcha):*\n_{orig_snippet}..._\n\n" if orig_snippet else ""
    )

    msg = (
        "🪄 *AI orqali qayta yozilgan variant (Oldin / Keyin):*\n\n"
        f"{orig_section}"
        f"✨ *Xatolari to'g'irlangan takomillashtirilgan namuna matn:*\n\n"
        f"{preview}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Repetitor maslahati:* Matnda imlo, tinish belgilari va gap bo'laklari bog'lanishidagi "
        "kamchiliklar to'g'rilandi. Fikrni dalillashda asardan iqtiboslar keltirish tavsiya etiladi."
    )
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👨‍🏫 Ustoz tekshiruviga yuborish",
                    callback_data=f"essay_review:{submission_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "📄 PDF xulosani yuklab olish",
                    callback_data=f"essay_pdf:{submission_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Natijaga qaytish", callback_data=f"essay_check:{submission_id}"
                )
            ],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
        ]
    )
    await send_reply(update, msg, parse_mode="Markdown", reply_markup=buttons)


async def essay_review_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, submission_id: int
) -> None:
    """Request teacher review for an essay submission."""
    query = update.callback_query
    user = await _get_or_create_user_async(update)
    if not user:
        if query:
            await query.answer("Foydalanuvchi aniqlanmadi")
        return

    if query:
        try:
            await query.answer()
        except Exception:
            pass

    from apps.essays.models import EssaySubmission
    from apps.essays.services import TeacherReviewService

    def _request():
        sub = EssaySubmission.objects.filter(id=submission_id, student=user).first()
        if not sub:
            return False, "Esse topilmadi."
        try:
            TeacherReviewService.request_teacher_review(
                sub, user, "Telegram bot orqali tekshirish so'rovi"
            )
            return True, None
        except Exception as exc:
            return False, str(exc)

    ok, err = await _run_db(_request)
    if not ok:
        msg = f"ℹ️ {err or 'Ustoz ko`rigini so`rashda xatolik yuz berdi.'}"
    else:
        msg = (
            "✅ *Ustoz ko'rigiga yuborildi!*\n\n"
            "Sizning essingiz o'qituvchiga tekshirish uchun taqdim etildi. "
            "O'qituvchi baholagach, xulosa shu yerga yuboriladi. 👨‍🏫"
        )

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔙 Natijaga qaytish", callback_data=f"essay_check:{submission_id}"
                )
            ],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
        ]
    )
    await send_reply(update, msg, parse_mode="Markdown", reply_markup=buttons)


async def essay_check_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, submission_id: int
) -> None:
    """Check essay grading status and show interactive action buttons."""
    query = update.callback_query
    user = await _get_or_create_user_async(update)
    if not user:
        if query:
            await query.answer("Foydalanuvchi aniqlanmadi")
        return

    if query:
        try:
            await query.answer()
        except Exception:
            pass

    from apps.essays.models import EssaySubmission

    sub = await _run_db(
        lambda: EssaySubmission.objects.filter(id=submission_id, student=user).first()
    )
    if not sub:
        await send_reply(
            update,
            "❌ Esse topilmadi.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")]]
            ),
        )
        return

    if sub.status in (EssaySubmission.Status.PENDING, EssaySubmission.Status.DRAFT):
        text = (
            "⏳ *Essangiz hali tekshirilmoqda...*\n\n"
            "AI tahlili fon rejimida davom etmoqda. Iltimos, birozdan so'ng qayta tekshiring:"
        )
        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔄 Qayta tekshirish",
                        callback_data=f"essay_check:{submission_id}",
                    )
                ],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
            ]
        )
        await send_reply(update, text, parse_mode="Markdown", reply_markup=buttons)
        return

    topic_title = sub.topic.title if sub.topic else "Erkin mavzu"
    score = str(sub.total_score) if sub.total_score is not None else "-"
    max_score = str(sub.max_score) if sub.max_score else "20"
    status_line = "✅ O'tdi" if sub.is_passed else "❌ O'tmadi"

    text = (
        f"📊 *ESSE NATIJASI (BMB 20 BALLIK SHKALA)*\n\n"
        f"📚 Mavzu: *{topic_title}*\n"
        f"📝 Holat: *{sub.get_status_display()}*\n"
        f"📊 Ball: *{score}/{max_score}*\n"
    )
    if sub.converted_score is not None:
        text += f"📈 Umumiy shkalada: *{sub.converted_score}/75*\n"
    text += f"📋 Natija: {status_line}\n\n"

    from apps.essays.models import EssayCriterionScore

    crit_maxes = EssayCriterionScore.CRITERION_MAX_SCORES

    def _get_criteria():
        return (
            list(sub.criteria.order_by("criterion_id"))
            if hasattr(sub, "criteria")
            else []
        )

    criteria_qs = await _run_db(_get_criteria)
    if criteria_qs:
        text += "📋 *12 Mezon bo'yicha tahlil:*\n"
        for c in criteria_qs[:12]:
            c_max = crit_maxes.get(c.criterion_id, 2.0)
            text += f"  • {c.criterion_id}. {c.name}: *{c.score}/{c_max}*\n"
        text += "\n"

    raw_res = sub.raw_result or {}
    spelling_errors = raw_res.get("spelling_errors", [])
    if spelling_errors:
        text += f"✍️ *Topilgan imlo xatolari ({len(spelling_errors)} ta):*\n"
        for se in spelling_errors[:4]:
            text += f"  • _{se.get('word', '')}_ ➔ *{se.get('correction', '')}* ({se.get('explanation', '')})\n"
        text += "\n"

    if sub.summary:
        text += f"💬 *Xulosa:* _{sub.summary}_\n\n"

    text += "Kerakli amalni tanlang 👇"

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🪄 AI tahririni ko'rish", callback_data=f"essay_improve:{sub.id}"
                ),
                InlineKeyboardButton(
                    "👨‍🏫 Ustoz tekshiruviga yuborish",
                    callback_data=f"essay_review:{sub.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📄 Batafsil PDF xulosa", callback_data=f"essay_pdf:{sub.id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🌐 Web'da ko'rish", url=f"{_site_url()}/essays/result/{sub.id}/"
                ),
                InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main"),
            ],
        ]
    )
    await send_reply(update, text, parse_mode="Markdown", reply_markup=buttons)


async def essay_pdf_download_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, submission_id: int
) -> None:
    """Generate and send official PDF certificate/result document directly to Telegram chat."""
    query = update.callback_query
    user = await _get_or_create_user_async(update)
    if not user:
        if query:
            await query.answer("Foydalanuvchi aniqlanmadi")
        return

    if query:
        try:
            await query.answer("📄 PDF sertifikat tayyorlanmoqda...")
        except Exception:
            pass

    from apps.essays.models import EssaySubmission
    from apps.essays.services import generate_essay_result_pdf

    def _gen():
        sub = EssaySubmission.objects.filter(id=submission_id, student=user).first()
        if not sub:
            return None, "Esse topilmadi."
        try:
            pdf_buf = generate_essay_result_pdf(sub)
            return (sub, pdf_buf), None
        except Exception as exc:
            return None, str(exc)

    res, err = await _run_db(_gen)
    if not res:
        await send_friendly_error(
            update, f"PDF yaratishda xatolik: {err or 'Esse topilmadi'}"
        )
        return

    sub, pdf_buf = res
    topic_title = sub.topic.title if sub.topic else "Erkin mavzu"
    score_str = f"{sub.total_score or 0}/{sub.max_score or 24}"
    caption = (
        f"📄 *ESSE TAHLILI VA SERTIFIKATI*\n\n"
        f"📚 Mavzu: *{topic_title}*\n"
        f"📊 Natija: *{score_str}* (75 lik shkalada: *{sub.converted_score or 0}*)\n"
        f"🎓 Rasmiy tekshiruv hujjati ilova qilindi."
    )
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🪄 AI orqali qayta yozish", callback_data=f"essay_improve:{sub.id}"
                ),
                InlineKeyboardButton(
                    "👨‍🏫 O'qituvchiga tekshirtirish",
                    callback_data=f"essay_review:{sub.id}",
                ),
            ],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
        ]
    )

    try:
        await context.bot.send_document(
            chat_id=user.telegram_chat_id,
            document=pdf_buf,
            filename=f"esse_sertifikat_{sub.id}.pdf",
            caption=caption,
            parse_mode="Markdown",
            reply_markup=buttons,
        )
    except Exception as exc:
        logger.exception("Failed to send essay PDF document: %s", exc)
        await send_friendly_error(update, f"PDF yuborishda xatolik yuz berdi: {exc}")


async def certificates_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /certificates — list user's earned certificates with download buttons."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    from apps.results.models import Certificate

    def _get_certs():
        return list(
            Certificate.objects.filter(student=user)
            .select_related("result__test", "result__course")
            .order_by("-issued_at")[:10]
        )

    certs = await _run_db(_get_certs)
    if not certs:
        await send_reply(
            update,
            "📜 *Sizda hali sertifikatlar yo'q.*\n\n"
            "Testlarni muvaffaqiyatli topshiring va rasmiy PDF sertifikatlarga ega bo'ling! 🎓",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🧠 Quiz topshirish", callback_data="menu_quiz"
                        )
                    ],
                    [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
                ]
            ),
        )
        return

    text = "📜 *Sizning sertifikatlaringiz:*\n\n"
    buttons = []
    for i, c in enumerate(certs, 1):
        c_title = (
            c.result.course.title
            if c.result and c.result.course
            else (c.result.test.title if c.result and c.result.test else "Kurs")
        )
        date_str = c.issued_at.strftime("%d.%m.%Y") if c.issued_at else ""
        text += (
            f"{i}. 🎓 *{c_title}*\n"
            f"   📋 Sertifikat: `{c.certificate_number}`\n"
            f"   📅 Berilgan: {date_str}\n\n"
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    f"📥 Yuklab olish ({c.certificate_number})",
                    callback_data=f"cert_dl:{c.id}",
                )
            ]
        )

    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")])
    await send_reply(
        update, text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def certificate_download_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, cert_id: int
) -> None:
    """Send certificate PDF document directly to Telegram chat."""
    query = update.callback_query
    user = await _get_or_create_user_async(update)
    if not user:
        if query:
            await query.answer("Foydalanuvchi aniqlanmadi")
        return

    if query:
        try:
            await query.answer("Sertifikat yuborilmoqda...")
        except Exception:
            pass

    from apps.results.models import Certificate
    from apps.certificates.services.generation import generate_certificate

    def _get_cert_path():
        cert = Certificate.objects.filter(id=cert_id, student=user).first()
        if not cert:
            return None, None
        if not cert.file and cert.result:
            try:
                generate_certificate(cert.result)
                cert.refresh_from_db()
            except Exception:
                pass
        if cert.file:
            return cert.file.path, cert.certificate_number
        return None, None

    cert_path, cert_num = await _run_db(_get_cert_path)
    if not cert_path or not update.effective_chat:
        await send_reply(update, "❌ Sertifikat fayli topilmadi.")
        return

    try:
        import os

        with open(cert_path, "rb") as doc_f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=doc_f,
                filename=os.path.basename(cert_path) or f"Sertifikat_{cert_num}.pdf",
                caption=f"📜 Sertifikat: *{cert_num}*",
                parse_mode="Markdown",
            )
    except Exception as exc:
        logger.exception("Sertifikat yuborishda xatolik: %s", exc)
        await send_reply(update, f"PDF yuborishda xatolik yuz berdi: {exc}")


async def myattendance_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /myattendance — display student attendance overview card."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    from apps.attendance.models import AttendanceRecord
    from django.db.models import Count, Q

    def _get_attendance():
        counts = AttendanceRecord.objects.filter(student=user).aggregate(
            present=Count("id", filter=Q(status=AttendanceRecord.Status.PRESENT)),
            late=Count("id", filter=Q(status=AttendanceRecord.Status.LATE)),
            absent=Count("id", filter=Q(status=AttendanceRecord.Status.ABSENT)),
            excused=Count("id", filter=Q(status=AttendanceRecord.Status.EXCUSED)),
        )
        total = (
            (counts.get("present") or 0)
            + (counts.get("late") or 0)
            + (counts.get("absent") or 0)
            + (counts.get("excused") or 0)
        )
        present_effective = (counts.get("present") or 0) + (counts.get("late") or 0)
        pct = round(present_effective / total * 100, 1) if total > 0 else 100.0
        return counts, total, pct

    counts, total, pct = await _run_db(_get_attendance)

    status_emoji = "🟢" if pct >= 80 else ("🟡" if pct >= 60 else "🔴")

    card = (
        f"📅 *DAVOMAT KARTASI*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 O'quvchi: *{user.get_full_name()}*\n"
        f"📈 Umumiy ko'rsatkich: {status_emoji} *{pct}%*\n"
        f"🔢 Jami qayd etilgan darslar: *{total} ta*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Kelgan: *{counts.get('present') or 0} ta*\n"
        f"⏰ Kechikkan: *{counts.get('late') or 0} ta*\n"
        f"📄 Sababli: *{counts.get('excused') or 0} ta*\n"
        f"❌ Kelmagan: *{counts.get('absent') or 0} ta*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💳 Kurs to'lovlari", callback_data="cb_tuition")],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
        ]
    )
    await send_reply(update, card, parse_mode="Markdown", reply_markup=keyboard)


# ---------------------------------------------------------------------------
# Arena 1v1 Bot Duel Handlers
# ---------------------------------------------------------------------------


async def arena_bot_start_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Start an interactive 1v1 Arena duel against AI bot in Telegram chat."""
    query = update.callback_query
    user = await _get_or_create_user_async(update)
    if not user:
        if query:
            await query.answer("Foydalanuvchi aniqlanmadi")
        return

    if query:
        try:
            await query.answer("⚔️ Duel tayyorlanmoqda...")
        except Exception:
            pass

    from apps.arena import services
    from apps.arena.models import ArenaQuestion

    def _setup():
        room = services.create_bot_room(user)
        q0 = ArenaQuestion.objects.filter(room=room, position=0).first()
        return room, q0

    room, q0 = await _run_db(_setup)
    if not room or not q0:
        await send_reply(update, "❌ Duel yaratishda xatolik yuz berdi.")
        return

    context.user_data["arena_duel"] = {
        "room_code": room.room_code,
        "current_idx": 0,
        "player_score": 0,
        "bot_score": 0,
        "player_correct": 0,
        "bot_correct": 0,
    }

    await _show_arena_question(
        update, context, room.room_code, q0, 0, room.total_questions
    )


async def _show_arena_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    room_code: str,
    q,
    idx: int,
    total: int,
) -> None:
    opt_a = getattr(q, "option_a", getattr(q, "choice_a", ""))
    opt_b = getattr(q, "option_b", getattr(q, "choice_b", ""))
    opt_c = getattr(q, "option_c", getattr(q, "choice_c", ""))
    opt_d = getattr(q, "option_d", getattr(q, "choice_d", ""))

    text = (
        f"⚔️ *ARENA DUEL — {idx + 1}/{total}-savol*\n"
        f"👤 Siz VS 🤖 Arena Bot\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"❓ *{q.question_text}*\n\n"
        f"A) {opt_a}\n"
        f"B) {opt_b}\n"
        f"C) {opt_c}\n"
        f"D) {opt_d}\n"
    )
    buttons = [
        [
            InlineKeyboardButton("A", callback_data=f"ar_ans:{room_code}:{idx}:a"),
            InlineKeyboardButton("B", callback_data=f"ar_ans:{room_code}:{idx}:b"),
        ],
        [
            InlineKeyboardButton("C", callback_data=f"ar_ans:{room_code}:{idx}:c"),
            InlineKeyboardButton("D", callback_data=f"ar_ans:{room_code}:{idx}:d"),
        ],
        [InlineKeyboardButton("❌ Duelni tark etish", callback_data="menu_arena")],
    ]
    await send_reply(
        update, text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def arena_answer_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    room_code: str,
    idx: int,
    choice: str,
) -> None:
    query = update.callback_query
    user = await _get_or_create_user_async(update)
    if not user:
        if query:
            await query.answer("Foydalanuvchi aniqlanmadi")
        return

    if query:
        try:
            await query.answer()
        except Exception:
            pass

    from apps.arena import services
    from apps.arena.models import ArenaRoom, ArenaQuestion

    def _process():
        room = ArenaRoom.objects.filter(room_code=room_code).first()
        if not room:
            return None
        q = ArenaQuestion.objects.filter(room=room, position=idx).first()
        if not q:
            return None

        player_res = (
            services.submit_answer(room, user.id, choice, idx, time_seconds=3.0) or {}
        )
        bot_user_id = room.player2_id
        bot_dec = services.bot_decide_answer(room, idx, bot_user_id)
        bot_res = (
            services.submit_answer(
                room,
                bot_user_id,
                bot_dec["answer"],
                idx,
                time_seconds=bot_dec.get("delay", 3.0),
            )
            or {}
        )

        return {
            "room": room,
            "q": q,
            "player_ok": player_res.get("is_correct", False),
            "player_pts": player_res.get("points", 0),
            "bot_ok": bot_res.get("is_correct", False),
            "bot_pts": bot_res.get("points", 0),
            "correct_ans": q.correct_answer.upper(),
        }

    res = await _run_db(_process)
    if not res:
        await send_reply(update, "Xatolik yuz berdi.")
        return

    duel_state = context.user_data.get("arena_duel", {})
    duel_state["player_score"] = duel_state.get("player_score", 0) + res["player_pts"]
    duel_state["bot_score"] = duel_state.get("bot_score", 0) + res["bot_pts"]
    if res["player_ok"]:
        duel_state["player_correct"] = duel_state.get("player_correct", 0) + 1
    if res["bot_ok"]:
        duel_state["bot_correct"] = duel_state.get("bot_correct", 0) + 1

    room = res["room"]
    next_idx = idx + 1
    total = room.total_questions

    p_icon = "✅" if res["player_ok"] else "❌"
    b_icon = "✅" if res["bot_ok"] else "❌"

    round_text = (
        f"🎯 *{idx + 1}-savol yakunlandi:*\n"
        f"To'g'ri javob: *{res['correct_ans']}*\n\n"
        f"👤 Siz: {p_icon} (+{res['player_pts']} ball)\n"
        f"🤖 Bot: {b_icon} (+{res['bot_pts']} ball)\n\n"
        f"📊 *Hisob:* Siz: *{duel_state['player_score']}* | Bot: *{duel_state['bot_score']}*"
    )

    if next_idx < total:
        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "➡️ Keyingi savol",
                        callback_data=f"ar_next:{room_code}:{next_idx}",
                    )
                ],
            ]
        )
    else:
        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🏁 Duelni yakunlash", callback_data=f"ar_finish:{room_code}"
                    )
                ],
            ]
        )

    await send_reply(update, round_text, parse_mode="Markdown", reply_markup=buttons)


async def arena_next_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    room_code: str,
    next_idx: int,
) -> None:
    query = update.callback_query
    if query:
        try:
            await query.answer()
        except Exception:
            pass

    from apps.arena.models import ArenaRoom, ArenaQuestion

    def _get_q():
        room = ArenaRoom.objects.filter(room_code=room_code).first()
        if not room:
            return None, None
        q = ArenaQuestion.objects.filter(room=room, position=next_idx).first()
        return room, q

    room, q = await _run_db(_get_q)
    if not room or not q:
        await send_reply(update, "Savol topilmadi.")
        return
    await _show_arena_question(
        update, context, room_code, q, next_idx, room.total_questions
    )


async def arena_finish_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    room_code: str,
) -> None:
    query = update.callback_query
    user = await _get_or_create_user_async(update)
    if not user:
        if query:
            await query.answer("Foydalanuvchi aniqlanmadi")
        return

    if query:
        try:
            await query.answer()
        except Exception:
            pass

    from apps.arena import services
    from apps.arena.models import ArenaRoom, ArenaProfile

    def _finish():
        room = ArenaRoom.objects.filter(room_code=room_code).first()
        if not room:
            return None
        profile_before = services.get_or_create_profile(user)
        old_rating = profile_before.rating
        services.finish_duel(room_code)
        profile_after = ArenaProfile.objects.get(user=user)
        new_rating = profile_after.rating
        return {
            "room": room,
            "old_rating": old_rating,
            "new_rating": new_rating,
            "streak": profile_after.current_win_streak,
        }

    res = await _run_db(_finish)
    duel_state = context.user_data.pop("arena_duel", {})
    p_score = duel_state.get("player_score", 0)
    b_score = duel_state.get("bot_score", 0)
    p_corr = duel_state.get("player_correct", 0)

    if res:
        diff = res["new_rating"] - res["old_rating"]
        diff_str = f"+{diff}" if diff >= 0 else str(diff)
        rating_line = f"🎯 ELO reyting: *{res['old_rating']} ➔ {res['new_rating']}* ({diff_str})\n"
        streak_line = f"🔥 Streak: *{res['streak']}*\n"
    else:
        rating_line = ""
        streak_line = ""

    if p_score > b_score:
        outcome = "🏆 *G'ALABA! Qoyilmaqom bellashuv!* 🎉"
    elif p_score == b_score:
        outcome = "🤝 *DURANG! Kuchlar teng keldi!*"
    else:
        outcome = "😔 *MAG'LUBIYAT! Keyingi safar albatta g'alaba qozonasiz!*"

    text = (
        f"🏁 *ARENA DUEL YAKUNLANDI!*\n\n"
        f"{outcome}\n\n"
        f"👤 Siz: *{p_score} ball* ({p_corr}/5)\n"
        f"🤖 Bot: *{b_score} ball*\n\n"
        f"{rating_line}"
        f"{streak_line}"
    )
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⚔️ Yangi duel", callback_data="arena_bot_start")],
            [InlineKeyboardButton("🏆 ELO Reyting", callback_data="arena_lb")],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
        ]
    )
    await send_reply(update, text, parse_mode="Markdown", reply_markup=buttons)


async def arena_invite_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Create a 1v1 Arena custom room and provide instant Telegram share invite link."""
    query = update.callback_query
    if query:
        try:
            await query.answer("⚔️ Xona yaratilmoqda...")
        except Exception:
            pass

    user = await _get_or_create_user_async(update)
    if not user:
        await send_friendly_error(
            update, "Foydalanuvchi ma'lumotlarini aniqlab bo'lmadi."
        )
        return

    from urllib.parse import quote_plus
    from django.conf import settings as _settings
    from apps.arena import services

    site_url = getattr(_settings, "SITE_URL", "https://grandec.uz").rstrip("/")

    try:
        room = await _run_db(services.create_custom_room, user)
    except Exception as exc:
        logger.exception("Failed to create custom arena room: %s", exc)
        await send_friendly_error(
            update, "Xona yaratishda xatolik yuz berdi.", retry_callback="arena_create"
        )
        return

    share_text = f"⚔️ Men bilan GRAND EDUCATION Quiz Arenada 1v1 bellashishga tayyormisan? Xona kodi: {room.room_code}"
    share_url = f"https://t.me/share/url?url={site_url}/arena/{room.room_code}/&text={quote_plus(share_text)}"

    msg_text = (
        f"⚔️ *DUEL XONASI YARATILDI!*\n\n"
        f"🔑 *Xona kodi:* `{room.room_code}`\n\n"
        f"Do'stingizni jangga chorlash uchun quyidagi tugmani bosing va unga taklif yuboring:\n\n"
        f"Do'stingiz ushbu havola orqali yoki botda `/arena_join {room.room_code}` buyrug'i bilan xonaga ulanishi mumkin."
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📲 Do'stni Telegram orqali chorlash", url=share_url
                )
            ],
            [
                InlineKeyboardButton(
                    "⚔️ Xonaga kirish (Web Arena)",
                    url=f"{site_url}/arena/{room.room_code}/",
                )
            ],
            [InlineKeyboardButton("🔙 Arenaga qaytish", callback_data="menu_arena")],
        ]
    )

    if query and query.message:
        try:
            await query.edit_message_text(
                msg_text, parse_mode="Markdown", reply_markup=keyboard
            )
            return
        except Exception:
            pass
    await send_reply(update, msg_text, parse_mode="Markdown", reply_markup=keyboard)


# ---------------------------------------------------------------------------
# Inline keyboard callback handlers
# ---------------------------------------------------------------------------


async def _dispatch_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE, handler
) -> None:
    """Dispatch to a handler that uses send_reply — safe from both message and callback.

    The handler must use send_reply() instead of update.message.reply_text().
    """
    await handler(update, context)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard callback queries with robust error & timeout catching."""
    query = update.callback_query
    if query:
        try:
            await query.answer()
        except Exception:
            pass

    data = query.data if query else ""

    try:
        if data == "menu_main":
            user = await _get_or_create_user_async(update)
            role = _get_user_role(
                user, update.effective_user.id if update.effective_user else None
            )
            if role == "admin":
                title = "👑 *GRAND EDUCATION* — Administrator boshqaruv paneli\n\nQuyidagi bo'limlardan foydalaning 👇"
            elif role == "teacher":
                title = "👨‍🏫 *GRAND EDUCATION* — O'qituvchi boshqaruv paneli\n\nQuyidagi bo'limlardan foydalaning 👇"
            else:
                title = "🎓 *Ona Tili & Adabiyot* — Bosh menyu\n\nQuyidagi tugmalardan foydalaning 👇"
            await query.edit_message_text(
                title,
                parse_mode="Markdown",
                reply_markup=_main_menu_keyboard(role),
            )
        elif data == "role_select_student":
            await role_select_student_callback(update, context)
        elif data == "role_select_teacher":
            await role_select_teacher_callback(update, context)
        elif data.startswith("adm_appr_tchr_"):
            target_id = int(data.removeprefix("adm_appr_tchr_"))
            await admin_approve_teacher_callback(update, context, target_id)
        elif data.startswith("adm_rej_tchr_"):
            target_id = int(data.removeprefix("adm_rej_tchr_"))
            await admin_reject_teacher_callback(update, context, target_id)
        elif data in ("menu_admin", "adm_main"):
            await admin_panel_handler(update, context)
        elif data == "adm_pending_receipts":
            await admin_pending_receipts_handler(update, context)
        elif data == "adm_stats":
            await admin_stats_handler(update, context)
        elif data == "adm_pending_teachers":
            await admin_pending_teachers_handler(update, context)
        elif data == "adm_settings":
            await admin_settings_handler(update, context)
        elif data == "adm_switch_student":
            user = await _get_or_create_user_async(update)
            role = _get_user_role(
                user, update.effective_user.id if update.effective_user else None
            )
            if role != "admin":
                await query.answer(
                    "⛔️ Bu buyruq faqat administratorlar uchun!", show_alert=True
                )
                return
            if query.message:
                await query.message.reply_text(
                    "🎓 O'quvchi rejimi ko'rinishi faollashtirildi 👇",
                    reply_markup=_persistent_menu_keyboard("student"),
                )
                await query.message.reply_text(
                    "🎓 *Ona Tili & Adabiyot* — O'quvchi boshqaruv paneli:",
                    parse_mode="Markdown",
                    reply_markup=_student_main_menu_keyboard(),
                )
        elif data == "adm_switch_teacher":
            user = await _get_or_create_user_async(update)
            role = _get_user_role(
                user, update.effective_user.id if update.effective_user else None
            )
            if role != "admin":
                await query.answer(
                    "⛔️ Bu buyruq faqat administratorlar uchun!", show_alert=True
                )
                return
            if query.message:
                await query.message.reply_text(
                    "👨‍🏫 O'qituvchi rejimi ko'rinishi faollashtirildi 👇",
                    reply_markup=_persistent_menu_keyboard("teacher"),
                )
                await query.message.reply_text(
                    "👨‍🏫 *GRAND EDUCATION* — O'qituvchi boshqaruv paneli:",
                    parse_mode="Markdown",
                    reply_markup=_teacher_main_menu_keyboard(),
                )
        elif data == "menu_teacher_newmock":
            await newmock_handler(update, context)
        elif data == "menu_teacher_excel":
            await teacher_excel_report_handler(update, context)
        elif data == "menu_teacher_attendance":
            await attendance_handler(update, context)
        elif data == "menu_teacher_reports":
            await group_report_handler(update, context)
        elif data == "menu_teacher_profile":
            await teacher_profile_handler(update, context)
        elif data.startswith("texcel_"):
            group_id = _safe_callback_int(data, prefix="texcel_")
            if group_id is not None:
                await teacher_group_excel_callback(update, context, group_id)
        elif data == "menu_mock_join":
            context.user_data["awaiting_mock_code"] = True
            text = (
                "📝 *MILLIY SERTIFIKAT MOCK TESTGA ULANISH*\n\n"
                "Ustozingiz bergan Mock kodini botga yuboring:\n"
                "Masalan: `#MOCK-401` yoki `MOCK-401`\n\n"
                "📌 Kodni yuborganingizdan so'ng, test darhol ochiladi va rasmiy BMB darajangiz (A+, A, B+...) hisoblab beriladi."
            )
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")]]
            )
            await query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=buttons
            )
        elif data == "menu_tests":
            from django.conf import settings as _settings

            site_url = getattr(_settings, "SITE_URL", "https://grandec.uz").rstrip("/")
            text = (
                "📚 *ONA TILI VA ADABIYOTIDAN TEST TOPSHIRISH*\n\n"
                "O'zingizga qulay test formatini tanlang:\n\n"
                "1️⃣ *📱 Fast CBT (Telegram Mini App)* — Telegram ichida sahifadan chiqmasdan tezkor '1 tadan ishlash' interfeysi.\n\n"
                "2️⃣ *🧠 Telegram Chat Quiz* — Telegram chatida savollar birma-bir beriladi, rasmiy BMB daraja hisoblanadi va AI xatolar tahlili beriladi.\n\n"
                "3️⃣ *📝 Mock Test (#kod)* — Ustozingiz bergan kod orqali mock imtihon topshirish."
            )
            buttons = [
                [
                    InlineKeyboardButton(
                        "📱 Fast CBT (Mini App)",
                        web_app={"url": f"{site_url}/tma/#/tests"},
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🧠 Telegram Chat Quiz", callback_data="menu_quiz"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📝 Mock Test (#kod orqali)", callback_data="menu_mock_join"
                    )
                ],
                [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
            ]
            await query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons)
            )

        elif data == "menu_quiz":
            from apps.notifications.bot.quiz import quiz_handler

            await _dispatch_handler(update, context, quiz_handler)
        elif data in ("menu_certs", "cb_certs"):
            await _dispatch_handler(update, context, certificates_handler)
        elif data in ("menu_myplan", "cb_myplan"):
            await _dispatch_handler(update, context, myplan_handler)
        elif data in ("menu_mytuition", "cb_mytuition", "cb_tuition"):
            await _dispatch_handler(update, context, mytuition_handler)
        elif data in ("menu_attendance", "cb_attendance"):
            await _dispatch_handler(update, context, myattendance_handler)
        elif data in ("menu_tournament", "cb_tournament"):
            await _dispatch_handler(update, context, tournament_handler)
        elif data in ("menu_parents", "cb_parents"):
            await _dispatch_handler(update, context, parent_start_handler)
        elif data.startswith("cb_topic_select:"):
            topic_id = int(data.split(":")[1])
            await essay_topic_select_callback(update, context, topic_id)
        elif data.startswith("essay_topic:"):
            topic_id = int(data.split(":")[1])
            await essay_topic_select_callback(update, context, topic_id)
        elif data.startswith("essay_improve:"):
            sub_id = int(data.split(":")[1])
            await essay_improve_callback(update, context, sub_id)
        elif data.startswith("essay_review:"):
            sub_id = int(data.split(":")[1])
            await essay_review_callback(update, context, sub_id)
        elif data.startswith("essay_check:"):
            sub_id = int(data.split(":")[1])
            await essay_check_callback(update, context, sub_id)
        elif data.startswith("essay_pdf:"):
            sub_id = int(data.split(":")[1])
            await essay_pdf_download_callback(update, context, sub_id)
        elif data == "arena_invite":
            await arena_invite_callback(update, context)
        elif data.startswith("cert_dl:"):
            cert_id = int(data.split(":")[1])
            await certificate_download_callback(update, context, cert_id)
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
        elif data == "cb_plans":
            await _dispatch_handler(update, context, plans_and_payment_handler)
        elif data in ("pay_plan_starter", "pay_plan_pro", "pay_plan_premium"):
            if data == "pay_plan_starter":
                selected_slug = "starter"
                plan_name = "Starter"
            elif data == "pay_plan_pro":
                selected_slug = "pro"
                plan_name = "Pro"
            else:
                selected_slug = "premium"
                plan_name = "Premium"

            context.user_data["selected_plan_slug"] = selected_slug
            context.user_data["payment_state"] = "awaiting_screenshot"
            from django.conf import settings as _settings

            card_number = (
                getattr(_settings, "PAYMENT_CARD_NUMBER", "") or "9860 **** **** ****"
            )
            card_holder = getattr(_settings, "PAYMENT_CARD_HOLDER", "") or "KOMILJON R"
            defaults = {"starter": 15000, "pro": 49000, "premium": 60000}
            price = (
                getattr(_settings, f"PLAN_{selected_slug.upper()}_PRICE", 0)
                or defaults[selected_slug]
            )
            text = (
                f"💳 To'lov uchun karta: `{card_number}`\n"
                f"👤 Egasi: {card_holder}\n"
                f"💎 Tarif: {plan_name}\n"
                f"💰 To'lov summasi: {price:,} so'm\n\n"
                f"To'lovni amalga oshirgach, chek skrinshotini ushbu chatga rasm qilib yuboring."
            )
            buttons = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Boshqa tarif tanlash", callback_data="cb_plans"
                        )
                    ]
                ]
            )
            await query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=buttons
            )
        elif data == "cb_limits":
            await _dispatch_handler(update, context, limits_handler)
        elif data == "cb_essay_text":
            await _handle_essay_text_choice(update, context)
        elif data == "cb_essay_image":
            await _handle_essay_image_choice(update, context)
        elif data == "cb_pages_more":
            await _handle_pages_more(update, context)
        elif data == "cb_pages_done":
            await _handle_pages_done(update, context)
        elif data == "cb_pages_cancel":
            await _handle_pages_cancel(update, context)
        elif data == "cb_ocr_confirm":
            await _handle_ocr_confirm(update, context)
        elif data == "cb_ocr_edit":
            await _handle_ocr_edit(update, context)
        elif data == "cb_ocr_retry":
            await _handle_ocr_retry(update, context)
        elif data.startswith("tg_buy_"):
            plan_id = _safe_callback_int(data, prefix="tg_buy_")
            if plan_id is not None:
                await _tg_buy_callback(update, context, plan_id)
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
        elif data.startswith("adm_rec_appr_"):
            receipt_id = _safe_callback_int(data, prefix="adm_rec_appr_")
            if receipt_id is not None:
                await approve_receipt_callback(update, context, receipt_id)
        elif data.startswith("adm_rec_rej_"):
            receipt_id = _safe_callback_int(data, prefix="adm_rec_rej_")
            if receipt_id is not None:
                await reject_receipt_callback(update, context, receipt_id)
        elif data.startswith("student_result_"):
            student_id = _safe_callback_int(data, prefix="student_result_")
            if student_id is not None:
                await _dispatch_handler(
                    update, context, lambda u, c: _show_student_detail(u, c, student_id)
                )
        # -- Teacher groups, attendance and group reports ------------------------
        elif data == "tgrplist":
            await _dispatch_handler(update, context, groups_handler)
        elif data.startswith("tgrp_"):
            group_id = _safe_callback_int(data, prefix="tgrp_")
            if group_id is not None:
                await _group_card_callback(update, context, group_id)
        elif data.startswith("tatt_"):
            group_id = _safe_callback_int(data, prefix="tatt_")
            if group_id is not None:
                await _attendance_callback(update, context, group_id)
        elif data.startswith("tmk_"):
            parsed = _parse_mark_callback(data)
            if parsed:
                await _mark_callback(update, context, *parsed)
        elif data.startswith("tall_"):
            session_id = _safe_callback_int(data, prefix="tall_")
            if session_id is not None:
                await _all_present_callback(update, context, session_id)
        elif data.startswith("tfinabs_"):
            session_id = _safe_callback_int(data, prefix="tfinabs_")
            if session_id is not None:
                await _finalize_callback(update, context, session_id, True)
        elif data.startswith("tfin_"):
            session_id = _safe_callback_int(data, prefix="tfin_")
            if session_id is not None:
                await _finalize_callback(update, context, session_id, False)
        elif data.startswith("trptw_"):
            group_id = _safe_callback_int(data, prefix="trptw_")
            if group_id is not None:
                await _attendance_report_callback(update, context, group_id, 7)
        elif data.startswith("trptm_"):
            group_id = _safe_callback_int(data, prefix="trptm_")
            if group_id is not None:
                await _attendance_report_callback(update, context, group_id, 30)
        elif data.startswith("trpt_"):
            group_id = _safe_callback_int(data, prefix="trpt_")
            if group_id is not None:
                await _attendance_report_callback(update, context, group_id)
        elif data.startswith("tstu_"):
            group_id = _safe_callback_int(data, prefix="tstu_")
            if group_id is not None:
                await _students_callback(update, context, group_id)
        elif data.startswith("terspend_"):
            group_id = _safe_callback_int(data, prefix="terspend_")
            if group_id is not None:
                await _essay_results_callback(
                    update, context, group_id, state="pending"
                )
        elif data.startswith("tersp_"):
            parts = data[len("tersp_") :].split("_")
            try:
                group_id, offset = int(parts[0]), int(parts[1])
            except (IndexError, TypeError, ValueError):
                logger.warning("Malformed essay page callback: %r", data)
            else:
                await _essay_results_callback(
                    update,
                    context,
                    group_id,
                    offset=max(0, offset),
                )
        elif data.startswith("ters_"):
            group_id = _safe_callback_int(data, prefix="ters_")
            if group_id is not None:
                await _essay_results_callback(update, context, group_id)
        elif data.startswith("tgreport_"):
            group_id = _safe_callback_int(data, prefix="tgreport_")
            if group_id is not None:
                await _group_report_callback(update, context, group_id)
        elif data == "tgrp_create_new":
            context.user_data["awaiting_create_group"] = True
            await edit_or_reply(
                update,
                "🏫 *Yangi guruh ochish*\n\n"
                "Iltimos, yangi guruhingiz nomini yozing:\n"
                "Masalan: `10-A Ona tili` yoki `Milliy Sertifikat Intensive`",
                parse_mode="Markdown",
            )
        elif data.startswith("ttuition_"):
            group_id = _safe_callback_int(data, prefix="ttuition_")
            if group_id is not None:
                await _tuition_group_callback(update, context, group_id)
        elif data.startswith("tuitpay_"):
            tuition_id = _safe_callback_int(data, prefix="tuitpay_")
            if tuition_id is not None:
                await _tuition_mark_paid_callback(update, context, tuition_id)
        elif data.startswith("thwadd_"):
            group_id = _safe_callback_int(data, prefix="thwadd_")
            await edit_or_reply(
                update,
                f"📚 *Uyga vazifa berish:*\n\n"
                f"Quyidagi buyruq orqali vazifa bering:\n"
                f"`/new_homework 44-rasmiy Mock test va Esse tahlili`",
                parse_mode="Markdown",
            )
        elif data.startswith("thw_"):
            group_id = _safe_callback_int(data, prefix="thw_")
            if group_id is not None:
                await _homework_group_callback(update, context, group_id)
        elif data == "tgrpleaderboard":
            await group_leaderboard_handler(update, context)
        elif data.startswith(("wr_att_", "wr_ess_", "wr_tst_", "wr_fin_", "wr_full_")):
            report_id = _safe_report_callback_id(data)
            if report_id is not None:
                section = next(
                    prefix
                    for prefix in (
                        "wr_att_",
                        "wr_ess_",
                        "wr_tst_",
                        "wr_fin_",
                        "wr_full_",
                    )
                    if data.startswith(prefix)
                )
                await _weekly_report_detail_callback(
                    update, context, report_id, section
                )
        else:
            # Unknown callback data — give user a main menu button
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")]]
            )
            if query:
                try:
                    await query.edit_message_text(
                        "ℹ️ Bu amal muddati tugagan yoki mavjud emas.\n"
                        "Bosh menyuga qaytishingiz mumkin 👇",
                        reply_markup=buttons,
                    )
                except Exception:
                    await send_reply(update, "Bosh menyu 👇", reply_markup=buttons)

    except Exception as exc:
        logger.exception("Error in callback query (%s): %s", data, exc)
        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")]]
        )
        try:
            if query and query.message:
                await query.message.reply_text(
                    "Operatsiyani bajarishda kutilmagan xatolik yuz berdi.\n"
                    "Bosh menyuga qaytib, qayta urinib ko'rishingiz mumkin 👇",
                    reply_markup=buttons,
                )
            else:
                await send_reply(
                    update,
                    "Operatsiyani bajarishda xatolik yuz berdi.\nBosh menyuga qaytish 👇",
                    reply_markup=buttons,
                )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# /leaderboard — ranking
# ---------------------------------------------------------------------------


async def leaderboard_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
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
                leaderboard.append(
                    {
                        "name": student.get_full_name() or student.email,
                        "total_xp": total_xp,
                        "total_coins": x.get("total_coins") or 0,
                        "test_count": test_count,
                        "test_avg": round(float(test_avg), 1),
                    }
                )

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
        medal = medals[i] if i < 3 else f"{i + 1}."
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
        today_start = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        )

        # Today's activity
        tests_today = Result.objects.filter(
            student=user, calculated_at__gte=today_start
        ).count()
        essays_today = EssaySubmission.objects.filter(
            student=user, submitted_at__gte=today_start
        ).count()
        games_today = UserGameScore.objects.filter(
            user=user, last_played_at__gte=today_start
        ).count()

        # Tasks
        tasks = []
        tasks.append(
            {
                "name": "1 ta test topshirish",
                "done": tests_today >= 1,
                "reward": "+10 XP",
            }
        )
        tasks.append(
            {"name": "1 ta esse yozish", "done": essays_today >= 1, "reward": "+15 XP"}
        )
        tasks.append(
            {"name": "1 ta o'yin o'ynash", "done": games_today >= 1, "reward": "+5 XP"}
        )
        tasks.append(
            {
                "name": "3 ta test topshirish",
                "done": tests_today >= 3,
                "reward": "+25 XP",
            }
        )

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
    """/premium — legacy alias for /plans.

    Grandec sells digital access, and Telegram's digital-goods rules require
    Telegram Stars for purchases made inside Telegram, so every purchase entry
    point routes to /plans. /plans issues an XTR invoice when a plan has a
    Stars price and otherwise states that Telegram sales are not configured —
    it never falls back to a card transfer.
    """
    await plans_handler(update, context)


# NOTE: the historical card-transfer helpers (buy_plan_callback,
# payment_screenshot_handler, approve/reject_payment_callback) are still
# registered and tested because the website's admin-verified receipt flow and
# the payment-approval pipeline use them. They are no longer reachable as a
# Telegram *purchase* path: /plans and /buy are Stars-only, so the
# ``buy_plan_<id>`` callback that armed the screenshot flow is never emitted.


# Payment card details — from settings (PAYMENT_CARD_*) with safe fallbacks
from django.conf import settings as _django_settings

PAYMENT_CARD = getattr(_django_settings, "PAYMENT_CARD_NUMBER", "")
PAYMENT_CARD_BANK = getattr(_django_settings, "PAYMENT_CARD_BANK", "")
PAYMENT_CARD_HOLDER = getattr(_django_settings, "PAYMENT_CARD_HOLDER", "")
PAYMENT_ADMIN_USERNAME = getattr(_django_settings, "PAYMENT_ADMIN_USERNAME", "")


async def buy_plan_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: int
) -> None:
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
    if not PAYMENT_CARD or not PAYMENT_CARD_BANK or not PAYMENT_CARD_HOLDER:
        await query.edit_message_text(
            "To'lov vaqtincha mavjud emas. Administrator bilan bog'laning."
        )
        return

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


async def omr_scan_prompt_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Prompt user to upload a photo of their OMR answer sheet."""
    context.user_data["omr_state"] = "awaiting_photo"
    text = (
        "📷 <b>Titul varaqa (OMR) avto-skaneri</b>\n\n"
        "Iltimos, o'quvchi to'ldirgan javoblar varaqasining (titul varaq) aniq va yorug' rasmini ushbu chatga yuboring.\n\n"
        "💡 <i>Tavsiyalar:</i>\n"
        "• Titul varaq to'g'ri burchak ostida suratga olingan bo'lsin\n"
        "• Test kodi (#MOCK-...) va belgilangan doirachalar aniq ko'rinsin\n"
        "• Tizim 2-3 soniyada to'g'ri kalitlar bilan solishtirib, to'liq tahlil va ballni chiqarib beradi!"
    )
    await send_reply(update, text, parse_mode="HTML")


async def omr_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Process uploaded OMR sheet photo, grade it, and reply with instant scorecard."""
    if not update.message or not update.message.photo:
        return False

    caption = (update.message.caption or "").lower()
    is_omr = context.user_data.get("omr_state") == "awaiting_photo" or any(
        w in caption for w in ("titul", "omr", "varaq", "answer sheet")
    )
    if not is_omr:
        return False

    context.user_data.pop("omr_state", None)
    status_msg = await update.message.reply_text(
        "⏳ <i>Titul varaqa skanerlanmoqda va doirachalar tahlil qilinmoqda...</i>",
        parse_mode="HTML",
    )

    try:
        photo = update.message.photo[-1]
        file_obj = await photo.get_file()
        file_bytes = await file_obj.download_as_bytearray()

        import io
        from apps.tests.omr_service import grade_omr_sheet

        user = await _get_or_create_user_async(update)
        img_buffer = io.BytesIO(file_bytes)
        img_buffer.name = "sheet.jpg"

        result = await _run_db(grade_omr_sheet, img_buffer, user=user)

        preview_lines = []
        for b in result.get("breakdown", [])[:15]:
            mark = "✅" if b["is_correct"] else "❌"
            preview_lines.append(
                f"{mark} {b['question_number']}-savol: Siz: {b['selected_answer']} (To'g'ri: {b['correct_answer']})"
            )

        preview_text = "\n".join(preview_lines)
        if len(result.get("breakdown", [])) > 15:
            preview_text += (
                f"\n<i>... va yana {len(result['breakdown']) - 15} ta savol</i>"
            )

        pass_badge = "🎉 O'TDI" if result.get("is_passed") else "⚠️ O'TMADI"

        msg = (
            f"✅ <b>Titul varaqa muvaffaqiyatli tekshirildi!</b>\n\n"
            f"📋 <b>Test:</b> {result.get('test_title', 'Mock Test')}\n"
            f"🎯 <b>Natija:</b> {result.get('correct_count')}/{result.get('total_questions')} ta to'g'ri ({result.get('percentage')}%)\n"
            f"🏅 <b>Daraja / Toifa:</b> {result.get('grade')}\n"
            f"⚡ <b>To'plangan XP:</b> +{result.get('xp_earned', 25)} XP (🔥 Streak yangilandi!)\n"
            f"Holat: <b>{pass_badge}</b>\n\n"
            f"<b>Savollar bo'yicha tahlil:</b>\n"
            f"{preview_text}\n\n"
            f"🔗 Saytda ko'rish: https://grandec.uz/tests/scan-omr/"
        )

        await status_msg.edit_text(msg, parse_mode="HTML")
        return True
    except Exception as e:
        logger.exception("OMR photo processing error: %s", e)
        await status_msg.edit_text(f"❌ Titul varaqani tahlil qilishda xatolik: {e}")
        return True


async def payment_screenshot_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle photo messages — check if it's a payment screenshot and create PaymentReceipt."""
    # Check if this photo is an OMR answer sheet
    if await omr_photo_handler(update, context):
        return

    # Never intercept essay image submissions
    if context.user_data.get(
        "essay_state"
    ) == "awaiting_photo" or context.user_data.get("active_topic_id"):
        return

    payment_state = context.user_data.get("payment_state")
    selected_slug = context.user_data.get("selected_plan_slug")
    caption = (update.message.caption or "").lower() if update.message else ""

    # Check if this is a payment receipt
    is_payment = (
        payment_state == "awaiting_screenshot"
        or selected_slug is not None
        or any(
            w in caption
            for w in (
                "chek",
                "to'lov",
                "tolov",
                "starter",
                "premium",
                "kvitansiya",
                "obuna",
            )
        )
    )
    if not is_payment:
        return

    user = await _get_or_create_user_async(update)
    if not user:
        return

    photo = update.message.photo[-1] if update.message.photo else None
    if not photo:
        await update.message.reply_text("Rasm topilmadi. Qaytadan yuboring.")
        return

    from django.conf import settings as _settings

    starter_price = getattr(_settings, "PLAN_STARTER_PRICE", 15000)
    pro_price = getattr(_settings, "PLAN_PRO_PRICE", 49000)
    premium_price = getattr(_settings, "PLAN_PREMIUM_PRICE", 60000)

    # Determine plan slug
    if not selected_slug:
        if "premium" in caption:
            selected_slug = "premium"
        elif "pro" in caption:
            selected_slug = "pro"
        else:
            selected_slug = "starter"

    price_map = {
        "starter": starter_price,
        "pro": pro_price,
        "premium": premium_price,
    }
    amount = Decimal(price_map.get(selected_slug, starter_price))

    # Download photo
    file_bytes = None
    try:
        file_obj = await photo.get_file()
        file_bytes = await file_obj.download_as_bytearray()
    except Exception as exc:
        logger.warning("Failed to download photo from telegram: %s", exc)

    if not file_bytes:
        await update.message.reply_text("Rasm yuklanmadi. Qaytadan yuboring.")
        return

    from apps.payments.services import (
        validate_and_hash_receipt_image,
        notify_admin_new_receipt,
    )

    try:
        image_hash, validated_bytes = await _run_db(
            validate_and_hash_receipt_image, bytes(file_bytes)
        )
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    def _create_receipt():
        from django.core.files.base import ContentFile
        from django.utils import timezone
        from apps.payments.models import PaymentReceipt

        filename = f"receipt_tg_{user.id}_{int(timezone.now().timestamp())}.jpg"
        content_file = ContentFile(validated_bytes, name=filename)

        receipt = PaymentReceipt.objects.create(
            user=user,
            plan=selected_slug,
            amount=amount,
            receipt_image=content_file,
            image_hash=image_hash,
            source=PaymentReceipt.Source.BOT,
            status=PaymentReceipt.Status.PENDING,
        )
        return receipt

    receipt = await _run_db(_create_receipt)

    # 4-MODUL & 3-MODUL: OCR tekshiruvi va guruh to'lovini avtomatik uzaytirish
    try:
        from apps.payments.receipt_scanner import scan_receipt_image
        from apps.courses.models import GroupEnrollment
        from apps.webapi.views_crm import send_telegram_message_safe

        ocr_res = scan_receipt_image(bytes(file_bytes))
        if ocr_res.get("is_valid") and ocr_res.get("amount", 0) >= 10000:
            def _apply_tuition_payment():
                enrollment = GroupEnrollment.objects.filter(student=user, is_active=True).first()
                if enrollment:
                    enrollment.record_payment(amount=ocr_res["amount"])
                    return enrollment
                return None

            enrollment = await _run_db(_apply_tuition_payment)
            if enrollment:
                amt_str = f"{ocr_res['amount']:,.0f} so'm".replace(",", " ")
                due_str = enrollment.next_payment_due.strftime("%d.%m.%Y")
                await update.message.reply_text(
                    f"✅ <b>To'lov chekingiz avtomatik OCR orqali tasdiqlandi!</b>\n\n"
                    f"👥 Guruh: <b>{enrollment.group.name}</b>\n"
                    f"💰 Qabul qilingan summa: <b>{amt_str}</b>\n"
                    f"🔢 Trans ID: <b>{ocr_res.get('transaction_id', 'UNKNOWN')}</b>\n"
                    f"📅 Keyingi to'lov sanangiz: <b>{due_str}</b> gacha uzaytirildi!\n\n"
                    f"Rahmat, darslaringizda omad tilaymiz!",
                    parse_mode=ParseMode.HTML,
                )
                # Ustoziga xabarnoma
                if enrollment.group.teacher and enrollment.group.teacher.telegram_chat_id:
                    t_msg = (
                        f"✅ <b>O'quvchi to'lov qildi! (OCR Chek)</b>\n\n"
                        f"👤 O'quvchi: <b>{user.get_full_name()}</b>\n"
                        f"👥 Guruh: <b>{enrollment.group.name}</b>\n"
                        f"💰 Summa: <b>{amt_str}</b>\n"
                        f"🔢 Trans ID: <b>{ocr_res.get('transaction_id', '')}</b>"
                    )
                    send_telegram_message_safe(enrollment.group.teacher.telegram_chat_id, t_msg)
    except Exception as e:
        logger.warning("OCR auto-apply tuition error: %s", e)

    try:
        await _run_db(notify_admin_new_receipt, receipt)
    except Exception as exc:
        logger.warning("Failed to notify admin of bot receipt #%s: %s", receipt.id, exc)

    # Clear state
    context.user_data.pop("payment_state", None)
    context.user_data.pop("selected_plan_slug", None)
    context.user_data.pop("selected_plan_id", None)

    plan_name = "Starter" if selected_slug == "starter" else "Premium"
    await update.message.reply_text(
        f"✅ Chekingiz qabul qilindi! Admin tasdiqlashi bilan obunangiz faollashadi.\n\n"
        f"📦 Tarif: *{plan_name}*\n"
        f"💰 Summa: *{int(amount):,} so'm*\n"
        f"📅 Sana: {receipt.created_at.strftime('%d.%m.%Y %H:%M')}",
        parse_mode="Markdown",
    )


async def _notify_admins_payment(
    update: Update, context: ContextTypes.DEFAULT_TYPE, payment_request
) -> None:
    """Notify platform administrators about a new payment request."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    from apps.payments.access import can_manage_payments

    def _get_admins():
        User = get_user_model()
        candidates = (
            User.objects.filter(
                Q(role="admin")
                | Q(is_superuser=True)
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

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Tasdiqlash",
                    callback_data=f"approve_payment_{payment_request.id}",
                ),
                InlineKeyboardButton(
                    "❌ Rad etish", callback_data=f"reject_payment_{payment_request.id}"
                ),
            ],
        ]
    )

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


async def approve_payment_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: int
) -> None:
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

        from apps.payments.models import (
            PaymentHistory,
            PaymentRequest,
            UserSubscription,
        )

        with transaction.atomic():
            # Row-lock the request so two admins approving the same payment
            # (or a concurrent reject) serialize; the status re-check inside
            # the lock makes the whole approve→subscribe→log flow atomic —
            # a crash mid-way can never leave a paid request un-activated.
            try:
                pr = PaymentRequest.objects.select_for_update().get(
                    id=payment_id, status="pending"
                )
            except PaymentRequest.DoesNotExist:
                return (
                    False,
                    "To'lov so'rovi topilmadi yoki allaqachon ko'rib chiqilgan.",
                )

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


async def reject_payment_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: int
) -> None:
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
                pr = PaymentRequest.objects.select_for_update().get(
                    id=payment_id, status="pending"
                )
            except PaymentRequest.DoesNotExist:
                return False, "To'lov so'rovi topilmadi."

            pr.status = "rejected"
            pr.reviewed_by = admin_user
            pr.reviewed_at = timezone.now()
            pr.admin_note = "Admin tomonidan rad etildi"
            pr.save(
                update_fields=["status", "reviewed_by", "reviewed_at", "admin_note"]
            )

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


async def approve_receipt_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, receipt_id: int
) -> None:
    """Handle adm_rec_appr_<id> — admin approves payment receipt."""
    query = update.callback_query
    from django.conf import settings

    admin_id = str(getattr(settings, "ADMIN_TELEGRAM_ID", "5582178765"))
    tg_uid = str(update.effective_user.id) if update.effective_user else ""
    admin_user = await _get_or_create_user_async(update)

    from apps.payments.access import can_manage_payments

    is_authorized = tg_uid == admin_id or (
        admin_user
        and (
            admin_user.is_staff
            or admin_user.is_superuser
            or getattr(admin_user, "role", "") == "admin"
            or can_manage_payments(admin_user)
        )
    )
    if not is_authorized:
        if query:
            try:
                await query.answer("Sizda ruxsat yo'q.", show_alert=True)
            except Exception:
                pass
        return

    from apps.payments.models import PaymentReceipt
    from apps.payments.services import approve_payment_receipt

    def _approve():
        from django.db import transaction

        with transaction.atomic():
            try:
                rec = PaymentReceipt.objects.select_for_update().get(
                    id=receipt_id, status=PaymentReceipt.Status.PENDING
                )
            except PaymentReceipt.DoesNotExist:
                return False, "To'lov cheki topilmadi yoki allaqachon ko'rib chiqilgan."
            approve_payment_receipt(rec, admin_user=admin_user)
            return True, rec

    success, result = await _run_db(_approve)

    admin_name = ""
    if update.effective_user:
        admin_name = (
            update.effective_user.first_name
            or update.effective_user.username
            or "Admin"
        )
    elif admin_user:
        admin_name = admin_user.get_full_name() or admin_user.username or "Admin"
    else:
        admin_name = "Admin"

    if success:
        note_text = f"\n\n✅ <b>Tasdiqlandi (Admin: {admin_name})</b>"
        if query and query.message:
            try:
                if getattr(query.message, "photo", None):
                    orig = query.message.caption_html or query.message.caption or ""
                    await query.edit_message_caption(
                        caption=f"{orig}{note_text}",
                        parse_mode="HTML",
                        reply_markup=None,
                    )
                else:
                    orig = query.message.text_html or query.message.text or ""
                    await query.edit_message_text(
                        text=f"{orig}{note_text}", parse_mode="HTML", reply_markup=None
                    )
            except Exception as e:
                logger.warning("Failed to edit admin receipt message: %s", e)
        if query:
            try:
                await query.answer("Chek muvaffaqiyatli tasdiqlandi!")
            except Exception:
                pass
    else:
        if query:
            try:
                await query.answer(str(result), show_alert=True)
            except Exception:
                pass


async def reject_receipt_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, receipt_id: int
) -> None:
    """Handle adm_rec_rej_<id> — admin rejects payment receipt."""
    query = update.callback_query
    from django.conf import settings

    admin_id = str(getattr(settings, "ADMIN_TELEGRAM_ID", "5582178765"))
    tg_uid = str(update.effective_user.id) if update.effective_user else ""
    admin_user = await _get_or_create_user_async(update)

    from apps.payments.access import can_manage_payments

    is_authorized = tg_uid == admin_id or (
        admin_user
        and (
            admin_user.is_staff
            or admin_user.is_superuser
            or getattr(admin_user, "role", "") == "admin"
            or can_manage_payments(admin_user)
        )
    )
    if not is_authorized:
        if query:
            try:
                await query.answer("Sizda ruxsat yo'q.", show_alert=True)
            except Exception:
                pass
        return

    from apps.payments.models import PaymentReceipt
    from apps.payments.services import reject_payment_receipt

    def _reject():
        from django.db import transaction

        with transaction.atomic():
            try:
                rec = PaymentReceipt.objects.select_for_update().get(
                    id=receipt_id, status=PaymentReceipt.Status.PENDING
                )
            except PaymentReceipt.DoesNotExist:
                return False, "To'lov cheki topilmadi yoki allaqachon ko'rib chiqilgan."
            reject_payment_receipt(
                rec, note="Admin tomonidan rad etildi", admin_user=admin_user
            )
            return True, rec

    success, result = await _run_db(_reject)

    admin_name = ""
    if update.effective_user:
        admin_name = (
            update.effective_user.first_name
            or update.effective_user.username
            or "Admin"
        )
    elif admin_user:
        admin_name = admin_user.get_full_name() or admin_user.username or "Admin"
    else:
        admin_name = "Admin"

    if success:
        note_text = f"\n\n❌ <b>Rad etildi (Admin: {admin_name})</b>"
        if query and query.message:
            try:
                if getattr(query.message, "photo", None):
                    orig = query.message.caption_html or query.message.caption or ""
                    await query.edit_message_caption(
                        caption=f"{orig}{note_text}",
                        parse_mode="HTML",
                        reply_markup=None,
                    )
                else:
                    orig = query.message.text_html or query.message.text or ""
                    await query.edit_message_text(
                        text=f"{orig}{note_text}", parse_mode="HTML", reply_markup=None
                    )
            except Exception as e:
                logger.warning("Failed to edit admin receipt message: %s", e)
        if query:
            try:
                await query.answer("Chek rad etildi.")
            except Exception:
                pass
    else:
        if query:
            try:
                await query.answer(str(result), show_alert=True)
            except Exception:
                pass


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

    site_url = getattr(_settings, "SITE_URL", "https://grandec.uz").rstrip("/")
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⚔️ Bot bilan duel (Telegram chatda)",
                    callback_data="arena_bot_start",
                )
            ],
            [
                InlineKeyboardButton(
                    "📲 Do'stni duelga chorlash (Xona yaratish)",
                    callback_data="arena_create",
                )
            ],
            [
                InlineKeyboardButton(
                    "🌐 Web Arenaga o'tish (Jonli 1v1)", url=f"{site_url}/arena/"
                )
            ],
            [
                InlineKeyboardButton("🏆 ELO Reyting", callback_data="arena_lb"),
                InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main"),
            ],
        ]
    )


async def arena_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /arena — show my ELO stats + top players + actions."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_friendly_error(
            update, "Foydalanuvchi ma'lumotlarini yuklashda xatolik yuz berdi."
        )
        return

    from apps.arena import services
    from apps.arena.models import ArenaProfile

    def _get_arena_data():
        profile = services.get_or_create_profile(user)
        rank = (
            ArenaProfile.objects.filter(
                user__is_bot=False, rating__gt=profile.rating
            ).count()
            + 1
        )
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

    await send_reply(
        update, text, parse_mode="Markdown", reply_markup=_arena_keyboard()
    )


async def arena_join_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /arena_join <CODE> — join a custom room by invite code."""
    user = await _get_or_create_user_async(update)
    if not user:
        await send_friendly_error(
            update, "Foydalanuvchi ma'lumotlarini yuklashda xatolik yuz berdi."
        )
        return

    from django.conf import settings as _settings

    site_url = getattr(_settings, "SITE_URL", "https://grandec.uz").rstrip("/")

    args = context.args if context.args else []
    if not args:
        await send_reply(
            update,
            "🔗 *Xonaga qo'shilish*\n\n"
            "Do'stingiz bergan invite kodni quyidagicha kiriting:\n"
            "`/arena_join KOD123`\n\n"
            "Yoki quyidagi tugma orqali Web Arenaga o'ting 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🌐 Web Arenaga o'tish", url=f"{site_url}/arena/"
                        )
                    ],
                    [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
                ]
            ),
        )
        return

    code = args[0].strip().upper()

    from apps.arena import services

    def _join():
        room, error = services.join_custom_room(code, user)
        return room, error

    try:
        room, error = await _run_db(_join)
    except Exception as exc:
        logger.exception("Error in arena_join_handler: %s", exc)
        await send_friendly_error(
            update, "Xonaga qo'shilishda kutilmagan xatolik yuz berdi."
        )
        return

    if room is None:
        await send_reply(
            update,
            f"❌ *Xonaga qo'shib bo'lmadi*\n\n{error or "Kod xato yoki xona to'la."}\n\n"
            f"To'g'ri kod bilan qayta urinib ko'ring: `/arena_join KOD`",
            parse_mode="Markdown",
            reply_markup=_error_keyboard(),
        )
        return

    await send_reply(
        update,
        f"✅ *Xonaga qo'shildingiz!*\n\n"
        f"🔑 Kod: `{room.room_code}`\n"
        f"⚔️ Duel boshlanmoqda — Web orqali kiring:\n"
        f"{site_url}/arena/{room.room_code}/",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⚔️ Arenaga o'tish", url=f"{site_url}/arena/{room.room_code}/"
                    )
                ],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")],
            ]
        ),
    )


async def arena_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle arena inline buttons (arena_create / arena_lb / arena_bot_start / ar_*)."""
    query = update.callback_query
    if query:
        try:
            await query.answer()
        except Exception:
            pass

    data = query.data if query else ""

    try:
        if data == "arena_bot_start":
            await arena_bot_start_callback(update, context)

        elif data.startswith("ar_ans:"):
            parts = data.split(":")
            room_code, idx, choice = parts[1], int(parts[2]), parts[3]
            await arena_answer_callback(update, context, room_code, idx, choice)

        elif data.startswith("ar_next:"):
            parts = data.split(":")
            room_code, next_idx = parts[1], int(parts[2])
            await arena_next_callback(update, context, room_code, next_idx)

        elif data.startswith("ar_finish:"):
            parts = data.split(":")
            room_code = parts[1]
            await arena_finish_callback(update, context, room_code)

        elif data in ("arena_create", "arena_invite"):
            await arena_invite_callback(update, context)

        elif data == "arena_lb":
            text = await _run_db(lambda: _arena_leaderboard_text(10))
            await query.edit_message_text(
                f"🏆 *ELO REYTING (TOP 10)*\n\n{text}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Orqaga", callback_data="menu_arena")]]
                ),
            )

        else:
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu_main")]]
            )
            await send_reply(update, "Arena amali yakunlangan.", reply_markup=buttons)

    except Exception as exc:
        logger.exception("Error in arena_callback_handler (%s): %s", data, exc)
        await send_friendly_error(update, "Arena duelida kutilmagan xatolik yuz berdi.")


# ---------------------------------------------------------------------------
# Teacher groups, attendance and group essay reports
# ---------------------------------------------------------------------------

#: Emoji used on the per-student marking buttons. The keyboard row order must
#: stay identical to the numbered roster in the message body, so the teacher
#: can read the list and tap the matching row.
_STATUS_EMOJI = {
    "present": "✅",
    "late": "⏰",
    "excused": "📄",
    "absent": "❌",
}
_STATUS_LEGEND = "✅ Keldi · ⏰ Kechikdi · 📄 Sababli · ❌ Kelmadi"

#: How many students a single marking keyboard shows per message.
_ATTENDANCE_PAGE_SIZE = 25
#: How many essay rows a single results message shows.
_ESSAY_PAGE_SIZE = 10


def _is_teacher_account(user, tg_id: int | None = None) -> bool:
    """Teachers, superadmin and platform admins may use the group commands."""
    from apps.accounts.access import is_platform_admin
    from django.conf import settings as _settings

    admin_id = int(getattr(_settings, "ADMIN_TELEGRAM_ID", SUPERADMIN_TELEGRAM_ID))

    if tg_id and int(tg_id) == admin_id:
        return True
    if user is None:
        return False
    if (
        getattr(user, "telegram_chat_id", None)
        and int(user.telegram_chat_id) == admin_id
    ):
        return True
    if (getattr(user, "role", None) or "").lower() in ("teacher", "admin"):
        return True
    return is_platform_admin(user)


async def _teacher_from_update(update: Update):
    """Resolve the linked teacher account, or reply and return ``None``.

    Authorization always goes through the canonical Grandec account linked to
    the Telegram identity — never through anything the sender typed.
    """
    user = await _get_or_create_user_async(update)
    if not user:
        await send_reply(update, "Hisobni aniqlab bo'lmadi. /start ni bosing.")
        return None
    tg_id = update.effective_user.id if update.effective_user else None
    if not await _run_db(_is_teacher_account, user, tg_id):
        await send_reply(
            update,
            "⛔️ Bu buyruq faqat o'qituvchilar uchun! "
            "Agar siz o'qituvchi bo'lsangiz, administrator bilan bog'laning.",
        )
        return None
    return user


async def _load_managed_group(user, group_id: int):
    """Fetch a group the user may manage, or ``None`` (never another teacher's)."""
    from apps.attendance.services import teacher_groups

    return await _run_db(lambda: teacher_groups(user).filter(pk=group_id).first())


def _group_list_keyboard(
    groups, callback_prefix: str = "tgrp_"
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"🏫 {g.name}", callback_data=f"{callback_prefix}{g.id}")]
        for g in groups
    ]
    rows.append(
        [InlineKeyboardButton("➕ Yangi guruh ochish", callback_data="tgrp_create_new")]
    )
    rows.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def _attendance_keyboard(session, rows) -> InlineKeyboardMarkup:
    """One status row per student, in the same order as the numbered roster."""
    keyboard = []
    for row in rows[:_ATTENDANCE_PAGE_SIZE]:
        student_id = row["student_id"]
        keyboard.append(
            [
                InlineKeyboardButton(
                    _STATUS_EMOJI[status],
                    callback_data=f"tmk_{session.id}_{student_id}_{status}",
                )
                for status in ("present", "late", "excused", "absent")
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                "✅ Hammasi keldi", callback_data=f"tall_{session.id}"
            ),
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton("💾 Yakunlash", callback_data=f"tfin_{session.id}"),
            InlineKeyboardButton("🏠 Guruh", callback_data=f"tgrp_{session.group_id}"),
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def _attendance_text(session, rows, data) -> str:
    lines = [
        f"🗓 *{data['group_name']}* — {data['lesson_date']} {data['time_label']}",
        "",
        f"👥 {data['roster_size']} o'quvchi · ✅ {data['present']} · "
        f"⏰ {data['late']} · 📄 {data['excused']} · ❌ {data['absent']}",
    ]
    if data["unmarked"]:
        lines.append(f"⚠️ Belgilanmagan: {data['unmarked']}")
    lines.append("")
    for index, row in enumerate(rows[:_ATTENDANCE_PAGE_SIZE], 1):
        emoji = _STATUS_EMOJI.get(row["status"], "➖") if row["marked"] else "➖"
        lines.append(f"{index}. {row['name']} — {emoji} {row['status_label']}")
    if len(rows) > _ATTENDANCE_PAGE_SIZE:
        lines.append("")
        lines.append(
            f"_(Qolgan {len(rows) - _ATTENDANCE_PAGE_SIZE} o'quvchi panel orqali "
            "belgilanadi.)_"
        )
    lines.append("")
    lines.append(_STATUS_LEGEND)
    return "\n".join(lines)


async def _render_attendance(update: Update, context, session) -> None:
    """Re-render the register with current statuses and live counts."""
    from apps.attendance.services import roster, summary

    rows = await _run_db(roster, session)
    data = await _run_db(summary, session)
    await edit_or_reply(
        update,
        _attendance_text(session, rows, data),
        parse_mode="Markdown",
        reply_markup=_attendance_keyboard(session, rows),
    )


@require_role("TEACHER")
async def groups_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/groups — the teacher's assigned groups."""
    user = await _teacher_from_update(update)
    if not user:
        return
    from apps.attendance.services import teacher_groups

    groups = await _run_db(lambda: list(teacher_groups(user).order_by("name")))
    if not groups:
        await send_reply(
            update,
            "🏫 Sizga hali guruh biriktirilmagan. Administrator bilan bog'laning.",
            reply_markup=_persistent_menu_keyboard("teacher"),
        )
        return
    lines = ["🏫 *Guruhlaringiz*", ""]
    for index, group in enumerate(groups, 1):
        count = await _run_db(lambda g=group: g.students.filter(is_active=True).count())
        invite = getattr(group, "invite_code", "") or f"GR-{group.id}"
        lines.append(f"{index}. *{group.name}* (Kod: `#{invite}`) — {count} o'quvchi")
    lines.append("")
    lines.append("Guruhni tanlang 👇")
    await send_reply(
        update,
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=_group_list_keyboard(groups),
    )


async def _send_group_card(update: Update, context, user, group) -> None:
    """Group overview: roster, today's attendance, essay counts, invite code."""
    from apps.attendance.services import summary, today_session
    from apps.essays.group_reports import group_essay_summary

    count = await _run_db(lambda: group.students.filter(is_active=True).count())
    session = await _run_db(today_session, group)
    if session is not None:
        data = await _run_db(summary, session)
        attendance_line = (
            f"✅ {data['present']} · ⏰ {data['late']} · 📄 {data['excused']} · "
            f"❌ {data['absent']}"
            + (f" · ⚠️ belgilanmagan: {data['unmarked']}" if data["unmarked"] else "")
        )
    else:
        attendance_line = "Bugun davomat olinmagan."
    essays = await _run_db(group_essay_summary, group)

    invite_code = getattr(group, "invite_code", "") or f"GR-{group.id}"
    text = (
        f"🏫 *{group.name}*\n\n"
        f"📌 Taklif kodi: `#{invite_code}`\n"
        f"_(O'quvchilar botga `#{invite_code}` deb yozsa, avtomatik guruhga qo'shiladi)_\n\n"
        f"👥 O'quvchilar soni: *{count} nafar*\n"
        f"🗓 Bugungi davomat: {attendance_line}\n"
        f"📝 Esse — baholangan: *{essays['graded']}*, kutilmoqda: "
        f"*{essays['pending']}*, topshirilmagan: *{essays['not_submitted']}*"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🗓 Davomat olish", callback_data=f"tatt_{group.id}"
                ),
                InlineKeyboardButton(
                    "💳 To'lov holati", callback_data=f"ttuition_{group.id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "👥 O'quvchilar va BMB", callback_data=f"tstu_{group.id}"
                ),
                InlineKeyboardButton("📚 Uyga vazifa", callback_data=f"thw_{group.id}"),
            ],
            [
                InlineKeyboardButton(
                    "📊 Excel hisobot (.xlsx)", callback_data=f"texcel_{group.id}"
                ),
                InlineKeyboardButton(
                    "📝 Esse natijalari", callback_data=f"ters_{group.id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📈 Davomat hisoboti", callback_data=f"trpt_{group.id}"
                ),
                InlineKeyboardButton(
                    "🏆 Guruhlar reytingi", callback_data="tgrpleaderboard"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📋 Taklif kodini ulashish",
                    url=f"https://t.me/share/url?url=%23{invite_code}&text={group.name}+guruhimizga+qo%27shiling!",
                ),
            ],
            [InlineKeyboardButton("🔙 Guruhlarim", callback_data="tgrplist")],
        ]
    )
    await edit_or_reply(update, text, parse_mode="Markdown", reply_markup=keyboard)


@require_role("TEACHER")
async def newmock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new mock test session from answer keys.
    Usage: /newmock 1a2b3c4d5a...40b
    """
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Ustoz, kalitlarni quyidagi formatda yuboring:\n"
            "`/newmock 1a2b3c4d5a...40b`\n\n"
            "Masalan: 40 ta savol uchun `1a2b3c4d...`",
            parse_mode="Markdown",
        )
        return

    key_str = args[0].strip()
    user = await _get_or_create_user_async(update)
    from apps.tests.mock_service import create_quick_mock

    try:
        res = await _run_db(create_quick_mock, user, key_str)
        code = res["mock_code"]
        await update.message.reply_text(
            f"✅ *Mock sessiya muvaffaqiyatli yaratildi!*\n\n"
            f"📌 Test kodi: `{code}`\n"
            f"🔢 Savollar: *{res['total_questions']} ta*\n"
            f"⏱ Vaqt: *{res['time_limit_minutes']} daqiqa*\n\n"
            f"O'quvchilaringizga ushbu kodni yuboring:\n"
            f"👉 O'quvchi botga `{code}` deb yozsa, darhol test boshlanadi!",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {e}")


async def _send_group_excel_document(
    update: Update, context: ContextTypes.DEFAULT_TYPE, group
) -> None:
    """Generate and send an Excel document (.xlsx) for a student group."""
    from apps.courses.group_service import export_group_to_excel
    import io

    excel_bytes = await _run_db(export_group_to_excel, group)
    f = io.BytesIO(excel_bytes)
    f.name = f"{group.name}_hisobot.xlsx"
    chat_id = (
        update.effective_chat.id if update.effective_chat else update.effective_user.id
    )
    await context.bot.send_document(
        chat_id=chat_id,
        document=f,
        filename=f"{group.name}_hisobot.xlsx",
        caption=f"📊 *{group.name}* guruhi o'quvchilari natijalari va monitoring hisoboti (Excel .xlsx).",
        parse_mode="Markdown",
    )


@require_role("TEACHER")
async def teacher_excel_report_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Send student report in Excel format for teacher groups."""
    user = await _get_or_create_user_async(update)
    from apps.attendance.services import teacher_groups

    groups = await _run_db(lambda: list(teacher_groups(user).order_by("name")))
    if not groups:
        await send_reply(
            update,
            "🏫 Sizga hali guruh biriktirilmagan. Excel hisobot olish uchun avval guruh yarating yoki administratorga murojaat qiling.",
            reply_markup=_persistent_menu_keyboard("teacher"),
        )
        return

    if len(groups) == 1:
        group = groups[0]
        await _send_group_excel_document(update, context, group)
        return

    buttons = [
        [InlineKeyboardButton(f"📊 {g.name} (Excel)", callback_data=f"texcel_{g.id}")]
        for g in groups
    ]
    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")])
    await send_reply(
        update,
        "📊 Qaysi guruhingiz hisobotini Excel formatida yuklab olmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@require_role("TEACHER")
async def teacher_group_excel_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, group_id: int
) -> None:
    """Handle texcel_<id> callback to export excel."""
    query = update.callback_query
    user = await _get_or_create_user_async(update)
    group = await _load_managed_group(user, group_id)
    if not group:
        if query:
            await query.answer(
                "Guruh topilmadi yoki sizga tegishli emas.", show_alert=True
            )
        return

    if query:
        await query.answer("Excel hisobot tayyorlanmoqda...")
    await _send_group_excel_document(update, context, group)


@require_role("TEACHER")
async def create_group_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Create a new group via /create_group <name> or start interactive name input."""
    user = await _teacher_from_update(update)
    if not user:
        return
    args = context.args or []
    if args:
        name = " ".join(args).strip()
        from apps.courses.models import StudentGroup

        grp = await _run_db(
            lambda: StudentGroup.objects.create(teacher=user, name=name)
        )
        invite_code = grp.invite_code or f"GR-{grp.id}"
        await update.message.reply_text(
            f"✅ *Yangi guruh muvaffaqiyatli ochildi!*\n\n"
            f"🏫 Guruh nomi: *{grp.name}*\n"
            f"📌 Taklif kodi: `#{invite_code}`\n\n"
            f"O'quvchilaringizga ushbu kodni yuboring. O'quvchi botga `#{invite_code}` deb yozishi "
            f"bilanoq guruhga qo'shiladi va unga avtomatik PRO tarifi beriladi!",
            parse_mode="Markdown",
            reply_markup=_persistent_menu_keyboard("teacher"),
        )
        return

    context.user_data["awaiting_create_group"] = True
    await update.message.reply_text(
        "🏫 *Yangi guruh ochish*\n\n"
        "Iltimos, ochmoqchi bo'lgan guruhingiz nomini yozing:\n"
        "Masalan: `10-A Ona tili` yoki `Milliy Sertifikat Intensive`",
        parse_mode="Markdown",
    )


async def _tuition_group_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, group_id: int
) -> None:
    """Show tuition billing status for students in the group with one-click payment toggle."""
    user = await _teacher_from_update(update)
    if not user:
        return
    group = await _load_managed_group(user, group_id)
    if not group:
        await edit_or_reply(update, "🏫 Guruh topilmadi yoki sizga tegishli emas.")
        return

    from datetime import date
    from apps.tuition.models import StudentTuition

    def _sync_and_get_tuition(grp):
        students = list(
            grp.students.filter(is_active=True).order_by("first_name", "last_name")
        )
        today = date.today()
        due_date = date(today.year, today.month, 20)
        recs = []
        for s in students:
            rec, _ = StudentTuition.objects.get_or_create(
                student=s,
                group=grp,
                due_date=due_date,
                defaults={
                    "monthly_fee": 400000,
                    "status": StudentTuition.Status.PENDING,
                },
            )
            recs.append(rec)
        return recs

    records = await _run_db(_sync_and_get_tuition, group)
    lines = [
        f"💳 *{group.name} — Oylik to'lovlar holati*",
        f"Standart oylik to'lov: *400 000 so'm* · Muddati: *20-sana*\n",
    ]

    unpaid_buttons = []
    paid_count = 0
    pending_count = 0

    for idx, tuit in enumerate(records, 1):
        s_name = tuit.student.get_full_name() or tuit.student.email
        fee_str = f"{tuit.monthly_fee:,}".replace(",", " ")
        if tuit.status == StudentTuition.Status.PAID:
            paid_count += 1
            lines.append(f"{idx}. *{s_name}* — {fee_str} so'm ✅ *(To'langan)*")
        else:
            pending_count += 1
            lines.append(f"{idx}. *{s_name}* — {fee_str} so'm ❌ *(Qarzdor)*")
            unpaid_buttons.append(
                [
                    InlineKeyboardButton(
                        f"✅ To'landi: {s_name[:18]}",
                        callback_data=f"tuitpay_{tuit.id}",
                    )
                ]
            )

    lines.append(f"\n📊 *Jami:* {paid_count} to'langan, {pending_count} qarzdor.")
    if pending_count > 0:
        lines.append("Quyidagi tugma orqali to'lovni 1-bosishda tasdiqlang 👇")

    keyboard_rows = unpaid_buttons[:8]
    keyboard_rows.append(
        [
            InlineKeyboardButton("🔄 Yangilash", callback_data=f"ttuition_{group.id}"),
            InlineKeyboardButton("🏠 Guruh", callback_data=f"tgrp_{group.id}"),
        ]
    )
    await edit_or_reply(
        update,
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )


async def _tuition_mark_paid_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, tuition_id: int
) -> None:
    """One-click payment confirmation by teacher with automatic student & parent notice."""
    query = update.callback_query
    from apps.tuition.models import StudentTuition
    from apps.accounts.models import ParentStudentRelation
    from apps.notifications.services.telegram_service import TelegramService

    def _mark_paid(t_id):
        tuit = (
            StudentTuition.objects.select_related("student", "group")
            .filter(id=t_id)
            .first()
        )
        if not tuit:
            return None
        tuit.mark_paid()
        return tuit

    tuit = await _run_db(_mark_paid, tuition_id)
    if not tuit:
        if query:
            await query.answer("To'lov yozuvi topilmadi.", show_alert=True)
        return

    student = tuit.student
    student_name = student.get_full_name() or student.email
    group_name = tuit.group.name
    fee_str = f"{tuit.monthly_fee:,}".replace(",", " ")

    if query:
        await query.answer(f"✅ {student_name} to'lovi tasdiqlandi!", show_alert=True)

    alert_text = (
        f"🎉 <b>To'lovingiz tasdiqlandi!</b>\n\n"
        f"Hurmatli <b>{student_name}</b>, ustozingiz <b>{group_name}</b> kursi uchun "
        f"oylik to'lovingizni (<b>{fee_str} so'm</b>) qabul qildi va tasdiqladi. Rahmat!\n\n"
        f"<i>GRAND EDUCATION</i>"
    )
    student_tg = getattr(student, "telegram_chat_id", None) or getattr(
        student, "telegram_id", None
    )
    if student_tg:
        try:
            TelegramService.send_message(
                chat_id=student_tg, text=alert_text, parse_mode="HTML"
            )
        except Exception:
            pass

    parent_rels = await _run_db(
        lambda: list(
            ParentStudentRelation.objects.filter(
                student=student, is_verified=True, parent_telegram_id__isnull=False
            )
        )
    )
    parent_alert_text = (
        f"🎉 <b>Hurmatli ota-ona!</b>\n\n"
        f"Farzandingiz <b>{student_name}</b>ning <b>{group_name}</b> kursi uchun oylik to'lovi (<b>{fee_str} so'm</b>) "
        f"ustoz tomonidan qabul qilindi va tasdiqlandi.\n\n"
        f"<i>GRAND EDUCATION Smart Monitoring</i>"
    )
    for rel in parent_rels:
        try:
            TelegramService.send_message(
                chat_id=rel.parent_telegram_id,
                text=parent_alert_text,
                parse_mode="HTML",
            )
        except Exception:
            pass

    await _tuition_group_callback(update, context, tuit.group_id)


async def group_leaderboard_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show learning center groups leaderboard based on average test scores."""
    from apps.courses.models import StudentGroup
    from apps.results.models import Result
    from django.db.models import Avg

    def _calc_leaderboard():
        groups = StudentGroup.objects.all().prefetch_related("students")
        board = []
        for g in groups:
            st_ids = list(
                g.students.filter(is_active=True).values_list("id", flat=True)
            )
            if not st_ids:
                continue
            avg_res = Result.objects.filter(student_id__in=st_ids).aggregate(
                avg=Avg("percentage")
            )["avg"]
            avg_pct = round(float(avg_res), 1) if avg_res else 0.0
            board.append(
                {
                    "group_name": g.name,
                    "teacher_name": g.teacher.get_full_name() or g.teacher.email,
                    "students_count": len(st_ids),
                    "avg_pct": avg_pct,
                }
            )
        board.sort(key=lambda x: x["avg_pct"], reverse=True)
        return board[:10]

    board = await _run_db(_calc_leaderboard)
    lines = [
        "🏆 *GRAND EDUCATION — GURUHLAR REYTINGI*",
        "Markazning eng yuqori o'zlashtirishga ega TOP-10 guruhlari:\n",
    ]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, item in enumerate(board):
        m = medals[i] if i < len(medals) else f"{i + 1}."
        from apps.tests.bmb_grading import calculate_bmb_grade

        grade = calculate_bmb_grade(item["avg_pct"])["grade"]
        lines.append(
            f"{m} *{item['group_name']}* — *{item['avg_pct']}%* (BMB: {grade})\n"
            f"   👨‍🏫 Ustoz: {item['teacher_name']} · {item['students_count']} o'quvchi\n"
        )
    if not board:
        lines.append("Hozircha guruhlar statistikasi shakllanmagan.")

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Guruhlarim", callback_data="tgrplist")]]
    )
    await edit_or_reply(
        update, "\n".join(lines), parse_mode="Markdown", reply_markup=keyboard
    )


@require_role("TEACHER")
async def export_group_report_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Export group report to Excel immediately via /export_group_report."""
    user = await _teacher_from_update(update)
    if not user:
        return
    from apps.attendance.services import teacher_groups

    groups = await _run_db(lambda: list(teacher_groups(user).order_by("name")))
    if not groups:
        await update.message.reply_text("Sizga tegishli guruh topilmadi.")
        return

    args = context.args or []
    target_group = None
    if args:
        try:
            raw_id = args[0].replace("#", "").replace("GR-", "").strip()
            gid = int(raw_id)
            target_group = next((g for g in groups if g.id == gid), None)
        except ValueError:
            pass
    if not target_group and len(groups) == 1:
        target_group = groups[0]

    if target_group:
        await update.message.reply_text(
            f"📊 *{target_group.name}* guruhi bo'yicha Excel hisobot tayyorlanmoqda...",
            parse_mode="Markdown",
        )
        await _send_group_excel_document(update, context, target_group)
    else:
        buttons = [
            [
                InlineKeyboardButton(
                    f"📊 {g.name} (Excel)", callback_data=f"texcel_{g.id}"
                )
            ]
            for g in groups
        ]
        await update.message.reply_text(
            "📊 *Qaysi guruhingiz hisobotini Excelda yuklamoqchisiz?*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )


async def _homework_group_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, group_id: int
) -> None:
    """Show homework assignments for the group."""
    user = await _teacher_from_update(update)
    if not user:
        return
    group = await _load_managed_group(user, group_id)
    if not group:
        await edit_or_reply(update, "🏫 Guruh topilmadi yoki sizga tegishli emas.")
        return

    from apps.courses.models import Homework

    def _get_hws():
        return list(Homework.objects.filter(group=group).order_by("-created_at")[:5])

    hws = await _run_db(_get_hws)
    lines = [f"📚 *{group.name} — Uyga vazifalar*", ""]
    if not hws:
        lines.append("Ushbu guruhga hali uyga vazifa berilmagan.\n")
        lines.append("Yangi vazifa berish uchun: `/new_homework <vazifa matni>`")
    else:
        for idx, hw in enumerate(hws, 1):
            due_str = hw.due_date.strftime("%d.%m.%Y %H:%M")
            lines.append(f"{idx}. *{hw.title}*\n   ⏰ Muddat: *{due_str}*\n")

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Yangi vazifa berish", callback_data=f"thwadd_{group.id}"
                )
            ],
            [InlineKeyboardButton("🏠 Guruh", callback_data=f"tgrp_{group.id}")],
        ]
    )
    await edit_or_reply(
        update, "\n".join(lines), parse_mode="Markdown", reply_markup=keyboard
    )


@require_role("TEACHER")
async def new_homework_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Create a homework assignment for the group: /new_homework <vazifa nomi>."""
    user = await _teacher_from_update(update)
    if not user:
        return
    from apps.attendance.services import teacher_groups

    groups = await _run_db(lambda: list(teacher_groups(user).order_by("name")))
    if not groups:
        await update.message.reply_text("Sizga tegishli guruh topilmadi.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "📚 *Uyga vazifa berish:*\n\n"
            "Quyidagi formatda yozing:\n"
            "`/new_homework 44-rasmiy Mock test va Esse tahlili`\n\n"
            "Muddat avtomatik ravishda 3 kun qilib belgilanadi va guruhdagi barcha o'quvchilarga Telegram orqali xabar boradi.",
            parse_mode="Markdown",
        )
        return

    hw_title = " ".join(args).strip()
    target_group = groups[0]  # Birinchi guruh

    from apps.courses.models import Homework
    from django.utils import timezone
    from datetime import timedelta
    from apps.notifications.services.telegram_service import TelegramService

    def _create_hw():
        due_date = timezone.now() + timedelta(days=3)
        hw = Homework.objects.create(
            group=target_group,
            title=hw_title,
            due_date=due_date,
            created_by=user,
        )
        students = list(target_group.students.filter(is_active=True))
        return hw, students

    hw, students = await _run_db(_create_hw)
    due_str = hw.due_date.strftime("%d.%m.%Y %H:%M")

    # O'quvchilarga xabar tarqatish
    notify_text = (
        f"📚 <b>Yangi uyga vazifa berildi!</b>\n\n"
        f"🏫 Guruh: <b>{target_group.name}</b>\n"
        f"📌 Vazifa: <b>{hw.title}</b>\n"
        f"⏰ Topshirish muddati (Deadline): <b>{due_str}</b>\n\n"
        f"<i>Vazifani o'z vaqtida bajarishingizni so'raymiz!</i>"
    )
    for s in students:
        s_tg = getattr(s, "telegram_chat_id", None) or getattr(s, "telegram_id", None)
        if s_tg:
            try:
                TelegramService.send_message(
                    chat_id=s_tg, text=notify_text, parse_mode="HTML"
                )
            except Exception:
                pass

    await update.message.reply_text(
        f"✅ *Uyga vazifa muvaffaqiyatli berildi!*\n\n"
        f"🏫 Guruh: *{target_group.name}*\n"
        f"📌 Vazifa: *{hw.title}*\n"
        f"⏰ Topshirish muddati: *{due_str}*\n"
        f"👥 *{len(students)} nafar* o'quvchiga eslatma yuborildi.",
        parse_mode="Markdown",
        reply_markup=_persistent_menu_keyboard("teacher"),
    )


@require_role("TEACHER")
async def teacher_test_bank_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show test bank for teachers."""
    from django.conf import settings as _settings

    site_url = getattr(_settings, "SITE_URL", "https://grandec.uz").rstrip("/")
    from apps.tests.models import Test

    test_count = await _run_db(lambda: Test.objects.filter(is_active=True).count())
    text = (
        f"📚 *TESTLAR BAZASI (GRAND EDUCATION)*\n\n"
        f"Tizimda jami faol testlar: *{test_count} ta*\n\n"
        f"Siz Fast CBT Mini App orqali barcha testlar savollarini ko'rishingiz "
        f"yoki yangi testlar tuzishingiz mumkin 👇"
    )
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📱 Fast CBT Testlar", web_app={"url": f"{site_url}/tma/#/tests"}
                )
            ],
            [
                InlineKeyboardButton(
                    "🌐 Web Testlar Banki", url=f"{site_url}/dashboard/"
                )
            ],
            [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
        ]
    )
    await send_reply(update, text, parse_mode="Markdown", reply_markup=buttons)


@require_role("TEACHER")
async def teacher_profile_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show teacher profile and statistics."""
    user = await _get_or_create_user_async(update)
    from apps.attendance.services import teacher_groups

    groups = await _run_db(lambda: list(teacher_groups(user)))
    group_count = len(groups)
    total_students = await _run_db(
        lambda: sum(g.students.filter(is_active=True).count() for g in groups)
    )
    from apps.tests.models import Test

    my_tests = await _run_db(lambda: Test.objects.filter(course__teacher=user).count())

    name = user.get_full_name() or user.first_name or "Ustoz"
    text = (
        f"👨‍🏫 *O'QITUVCHI SHAXSIY KABINETI*\n\n"
        f"👤 Ustoz: *{name}*\n"
        f"🎭 Rol: *O'qituvchi (TEACHER)*\n"
        f"🆔 Telegram ID: `{user.telegram_chat_id}`\n\n"
        f"📊 *Faoliyat statistikasi:*\n"
        f"• 🏫 Biriktirilgan guruhlar: *{group_count} ta*\n"
        f"• 👥 Jami o'quvchilar: *{total_students} nafar*\n"
        f"• 📝 Mualliflik testlari: *{my_tests} ta*\n"
    )
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👥 Guruhlarim", callback_data="tgrplist")],
            [
                InlineKeyboardButton(
                    "📝 Yangi Mock yaratish", callback_data="menu_teacher_newmock"
                )
            ],
            [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
        ]
    )
    await send_reply(update, text, parse_mode="Markdown", reply_markup=buttons)


# ---------------------------------------------------------------------------
# First-Time Onboarding & Role Selection Callbacks
# ---------------------------------------------------------------------------


async def role_select_student_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback when a new user selects '🎓 Men o'quvchiman'."""
    query = update.callback_query
    if query:
        try:
            await query.answer()
        except Exception:
            pass

    user = await _get_or_create_user_async(update)
    if not user:
        return

    def _set_student():
        from apps.accounts.models import User as UserModel

        user.role = UserModel.Role.STUDENT
        user.save(update_fields=["role"])

    await _run_db(_set_student)

    welcome = (
        f"Salom, *{user.first_name}*! 👋\n\n"
        f"🎓 *Ona Tili & Adabiyot* — Ta'lim platformasining rasmiy boti.\n\n"
        f"Siz muvaffaqiyatli *O'quvchi* sifatida ro'yxatdan o'tdingiz!\n\n"
        f"Bu yerda:\n"
        f"• ✍️ *Esse yozish* (AI baholaydi, takomillashtiradi)\n"
        f"• 🧠 *Telegram Quiz* va testlar topshirish\n"
        f"• ⚔️ *Arena 1v1* duellarida bellashish\n"
        f"• 📜 *Sertifikatlarni* to'g'ridan-to'g'ri PDF yuklab olish\n"
        f"• 📊 To'lov va davomat monitoringi\n\n"
        f"Quyidagi menyudan kerakli bo'limni tanlang 👇"
    )
    if query:
        try:
            await query.edit_message_text(
                welcome,
                parse_mode="Markdown",
                reply_markup=_student_main_menu_keyboard(),
            )
        except Exception:
            pass
        if query.message:
            await query.message.reply_text(
                "Quyidagi menyu tugmalaridan foydalanishingiz mumkin 👇",
                reply_markup=_persistent_menu_keyboard("student"),
            )


async def role_select_teacher_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback when a user selects '👨‍🏫 Men o'qituvchiman'."""
    query = update.callback_query
    if query:
        try:
            await query.answer()
        except Exception:
            pass

    await _get_or_create_user_async(update)
    tg_user = update.effective_user

    from django.conf import settings as _settings

    admin_id = int(getattr(_settings, "ADMIN_TELEGRAM_ID", SUPERADMIN_TELEGRAM_ID))
    # Notify admin
    try:
        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"👨‍🏫 <b>Yangi o'qituvchi arizasi!</b>\n\n"
                f"👤 Ism: <b>{tg_user.first_name} {tg_user.last_name or ''}</b>\n"
                f"🆔 Telegram ID: <code>{tg_user.id}</code>\n"
                f"📱 Username: @{tg_user.username or "yo'q"}\n\n"
                f"Ushbu foydalanuvchini o'qituvchi sifatida tasdiqlaysizmi?"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Tasdiqlash", callback_data=f"adm_appr_tchr_{tg_user.id}"
                        ),
                        InlineKeyboardButton(
                            "❌ Rad etish", callback_data=f"adm_rej_tchr_{tg_user.id}"
                        ),
                    ]
                ]
            ),
        )
    except Exception as e:
        logger.warning("Failed to notify admin of teacher request: %s", e)

    msg = (
        "👨‍🏫 *O'qituvchilik arizangiz qabul qilindi!*\n\n"
        "Arizangiz administratorga ko'rib chiqish uchun yuborildi. "
        "Administrator tasdiqlagach, barcha o'qituvchi imkoniyatlari ochiladi.\n\n"
        "Agar siz platformada allaqachon o'qituvchi bo'lsangiz, "
        "telefon raqamingizni yuborib tezkor tekshirishdan o'tishingiz mumkin 👇"
    )
    if query:
        try:
            await query.edit_message_text(msg, parse_mode="Markdown")
        except Exception:
            pass
        if query.message:
            context.user_data["awaiting_teacher_contact"] = True
            contact_kb = ReplyKeyboardMarkup(
                [[KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await query.message.reply_text(
                "Telefon raqamingizni ulashing:", reply_markup=contact_kb
            )


async def admin_approve_teacher_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, target_tg_id: int
) -> None:
    """Admin approves a teacher application."""
    query = update.callback_query
    from django.conf import settings as _settings

    admin_id = int(getattr(_settings, "ADMIN_TELEGRAM_ID", SUPERADMIN_TELEGRAM_ID))
    if not (update.effective_user and update.effective_user.id == admin_id):
        if query:
            await query.answer("Sizda ruxsat yo'q.", show_alert=True)
        return

    def _do_approve():
        from apps.accounts.models import User as UserModel

        u = UserModel.objects.filter(telegram_chat_id=target_tg_id).first()
        if u:
            u.role = UserModel.Role.TEACHER
            u.save(update_fields=["role"])
            return u
        return None

    await _run_db(_do_approve)
    if query:
        await query.answer("O'qituvchi tasdiqlandi!")
        try:
            await query.edit_message_text(
                f"✅ O'qituvchi muvaffaqiyatli tasdiqlandi (TG ID: {target_tg_id})"
            )
        except Exception:
            pass

    try:
        await context.bot.send_message(
            chat_id=target_tg_id,
            text=(
                "🎉 *Tabriklaymiz! O'qituvchi arizangiz tasdiqlandi!*\n\n"
                "Endi siz guruhlar yaratishingiz, /newmock orqali test tuzishingiz "
                "va o'quvchilar hisobotini Excel formatida olishingiz mumkin.\n\n"
                "Boshlash uchun /start buyrug'ini bosing!"
            ),
            parse_mode="Markdown",
            reply_markup=_persistent_menu_keyboard("teacher"),
        )
    except Exception as e:
        logger.warning("Could not notify teacher %d: %s", target_tg_id, e)


async def admin_reject_teacher_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, target_tg_id: int
) -> None:
    """Admin rejects a teacher application."""
    query = update.callback_query
    from django.conf import settings as _settings

    admin_id = int(getattr(_settings, "ADMIN_TELEGRAM_ID", SUPERADMIN_TELEGRAM_ID))
    if not (update.effective_user and update.effective_user.id == admin_id):
        if query:
            await query.answer("Sizda ruxsat yo'q.", show_alert=True)
        return

    if query:
        await query.answer("Ariza rad etildi.")
        try:
            await query.edit_message_text(
                f"❌ O'qituvchi arizasi rad etildi (TG ID: {target_tg_id})"
            )
        except Exception:
            pass

    try:
        await context.bot.send_message(
            chat_id=target_tg_id,
            text="❌ O'qituvchilik arizangiz rad etildi.",
            reply_markup=_persistent_menu_keyboard("student"),
        )
    except Exception as e:
        logger.warning("Could not notify user %d: %s", target_tg_id, e)


# ---------------------------------------------------------------------------
# Superadmin Handlers
# ---------------------------------------------------------------------------


@require_role("ADMIN")
async def admin_panel_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Admin command: /admin"""
    await send_reply(
        update,
        "👑 *GRAND EDUCATION — SUPERADMIN BOSHQARUV PANELI*\n\n"
        "Quyidagi bo'limlardan birini tanlang 👇",
        parse_mode="Markdown",
        reply_markup=_admin_main_menu_keyboard(),
    )


@require_role("ADMIN")
async def admin_pending_receipts_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """List pending payment receipts for admin verification."""
    from apps.payments.models import PaymentReceipt

    receipts = await _run_db(
        lambda: list(
            PaymentReceipt.objects.filter(status=PaymentReceipt.Status.PENDING)
            .select_related("user")
            .order_by("-id")[:5]
        )
    )
    if not receipts:
        await send_reply(
            update,
            "✅ *Kutilayotgan yangi to'lov cheklari mavjud emas!*",
            parse_mode="Markdown",
            reply_markup=_admin_main_menu_keyboard(),
        )
        return

    text_lines = [f"📥 *KUTILAYOTGAN TO'LOV CHEKLARI ({len(receipts)} ta)*\n"]
    buttons = []
    for r in receipts:
        user_name = r.user.get_full_name() or r.user.email
        text_lines.append(
            f"• ID #{r.id} | {user_name} | Tarif: *{r.plan}* | {r.amount} so'm"
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    f"✅ #{r.id} Tasdiqlash", callback_data=f"adm_rec_appr_{r.id}"
                ),
                InlineKeyboardButton(
                    f"❌ #{r.id} Rad etish", callback_data=f"adm_rec_rej_{r.id}"
                ),
            ]
        )
    buttons.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="menu_admin")])
    await send_reply(
        update,
        "\n".join(text_lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@require_role("ADMIN")
async def admin_stats_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display overall system statistics for superadmin."""
    from apps.accounts.models import User as UserModel
    from apps.results.models import Result
    from apps.essays.models import EssaySubmission
    from apps.payments.models import PaymentReceipt
    from apps.courses.models import StudentGroup

    total_users = await _run_db(UserModel.objects.count)
    students = await _run_db(lambda: UserModel.objects.filter(role="student").count())
    teachers = await _run_db(lambda: UserModel.objects.filter(role="teacher").count())
    groups = await _run_db(StudentGroup.objects.count)
    results = await _run_db(Result.objects.count)
    essays = await _run_db(EssaySubmission.objects.count)
    pending_receipts = await _run_db(
        lambda: PaymentReceipt.objects.filter(status="pending").count()
    )

    stats_msg = (
        "📈 *GRAND EDUCATION — UMUMIY STATISTIKA*\n\n"
        f"👥 Jami foydalanuvchilar: *{total_users:,}*\n"
        f"🎓 O'quvchilar: *{students:,}*\n"
        f"👨‍🏫 O'qituvchilar: *{teachers:,}*\n"
        f"🏫 Guruhlar: *{groups:,}*\n\n"
        f"📝 Yozilgan esselar: *{essays:,}*\n"
        f"📚 Topshirilgan testlar: *{results:,}*\n"
        f"💳 Kutilayotgan to'lov cheklari: *{pending_receipts} ta*\n\n"
        f"⚡️ Server holati: *Online (200 OK)*"
    )
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔄 Yangilash", callback_data="adm_stats")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="menu_admin")],
        ]
    )
    await send_reply(update, stats_msg, parse_mode="Markdown", reply_markup=buttons)


@require_role("ADMIN")
async def admin_pending_teachers_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display teacher approval management."""
    text = (
        "👨‍🏫 *O'QITUVCHILARNI TASDIQLASH VA TAYINLASH*\n\n"
        "O'qituvchi bo'lishni xohlagan foydalanuvchi /start orqali 'Men o'qituvchiman' ni tanlaganda, "
        "adminga tasdiqlash so'rovi yuboriladi.\n\n"
        "Istalgan foydalanuvchini darhol o'qituvchiga aylantirish uchun quyidagi buyruqdan foydalaning:\n"
        "`/promote_teacher <telegram_id yoki email>`"
    )
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="menu_admin")],
        ]
    )
    await send_reply(update, text, parse_mode="Markdown", reply_markup=buttons)


@require_role("ADMIN")
async def admin_settings_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display system settings."""
    text = (
        "⚙️ *TIZIM SOZLAMALARI (GRAND EDUCATION)*\n\n"
        "• Bot: `@uz_essaygrader_bot`\n"
        "• Platforma: `grandec.uz`\n"
        "• Superadmin ID: `5582178765`\n"
        "• RBAC Holati: *Faol (Strict Mode)*\n"
        "• Ma'lumotlar bazasi: PostgreSQL (Healthy)\n"
        "• Kesh & Navbat: Redis + Celery (Healthy)\n"
    )
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="menu_admin")],
        ]
    )
    await send_reply(update, text, parse_mode="Markdown", reply_markup=buttons)


@require_role("ADMIN")
async def promote_teacher_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Admin command: /promote_teacher <telegram_id or email>"""
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Format: `/promote_teacher <telegram_id yoki email>`", parse_mode="Markdown"
        )
        return
    query_str = args[0].strip()

    def _promote_by_query():
        from apps.accounts.models import User as UserModel

        if query_str.isdigit():
            u = UserModel.objects.filter(telegram_chat_id=int(query_str)).first()
        else:
            u = UserModel.objects.filter(email__iexact=query_str).first()
        if not u:
            return None
        u.role = UserModel.Role.TEACHER
        u.save(update_fields=["role"])
        return u

    u = await _run_db(_promote_by_query)
    if u:
        await update.message.reply_text(
            f"✅ Foydalanuvchi *{u.get_full_name() or u.email}* muvaffaqiyatli O'QITUVCHI roliga o'tkazildi!",
            parse_mode="Markdown",
        )
        if u.telegram_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=u.telegram_chat_id,
                    text="🎉 Administrator sizga O'QITUVCHI rolini berdi! /start ni bosing.",
                    reply_markup=_persistent_menu_keyboard("teacher"),
                )
            except Exception:
                pass
    else:
        await update.message.reply_text(f"❌ Foydalanuvchi '{query_str}' topilmadi.")


@require_role("TEACHER")
async def attendance_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/attendance — choose a group, then take the register."""
    user = await _teacher_from_update(update)
    if not user:
        return
    from apps.attendance.services import teacher_groups

    groups = await _run_db(lambda: list(teacher_groups(user).order_by("name")))
    if not groups:
        await send_reply(update, "🏫 Sizga guruh biriktirilmagan.")
        return

    await send_reply(
        update,
        "🗓 *Qaysi guruh uchun davomat olasiz?*",
        parse_mode="Markdown",
        reply_markup=_group_list_keyboard(groups, callback_prefix="tatt_"),
    )


async def _start_attendance(update: Update, context, user, group) -> None:
    """Create (idempotently) today's register and render the marking keyboard."""
    from apps.attendance.services import AttendanceError, create_session

    # A redelivered callback must not open a second register for the same
    # group/day: the key is derived from the update identity.
    update_id = getattr(update, "update_id", None) or getattr(
        getattr(update, "callback_query", None),
        "id",
        None,
    )
    key = (
        f"tatt:{getattr(update.effective_user, 'id', 0)}:{update_id}"
        if update_id
        else None
    )
    try:
        session, _created = await _run_db(
            lambda: create_session(
                group=group,
                teacher=user,
                actor=user,
                idempotency_key=key,
            )
        )
    except AttendanceError as exc:
        await send_reply(update, exc.messages[0] if exc.messages else "Xatolik.")
        return
    except PermissionDenied:
        await send_reply(update, "Bu guruh sizga tegishli emas.")
        return

    from apps.attendance.models import AttendanceSession

    if session.status == AttendanceSession.Status.FINALIZED:
        await edit_or_reply(
            update,
            f"ℹ️ *{group.name}* uchun bugungi davomat allaqachon yakunlangan.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📊 Hisobot", callback_data=f"trpt_{group.id}"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "🏠 Guruh", callback_data=f"tgrp_{group.id}"
                        ),
                    ],
                ]
            ),
        )
        return

    await _render_attendance(update, context, session)


async def _mark_student(
    update: Update, context, user, session_id: int, student_id: int, status: str
) -> None:
    """Apply one status tap and re-render the register."""
    from apps.attendance.models import AttendanceRecord
    from apps.attendance.services import (
        AttendanceError,
        get_session_for_user,
        mark,
    )

    if status not in dict(AttendanceRecord.Status.choices):
        await send_reply(update, "Noma'lum davomat holati.")
        return
    try:
        session = await _run_db(get_session_for_user, user, session_id)
        student = await _run_db(
            lambda: session.group.students.filter(pk=student_id).first()
        )
        if student is None:
            await send_reply(update, "O'quvchi topilmadi.")
            return
        await _run_db(mark, session, student, status, actor=user)
    except AttendanceError as exc:
        await send_reply(update, exc.messages[0] if exc.messages else "Xatolik.")
        return
    except PermissionDenied:
        await send_reply(update, "Bu davomat darsi sizga tegishli emas.")
        return
    await _render_attendance(update, context, session)


async def _mark_all_present(update: Update, context, user, session_id: int) -> None:
    from apps.attendance.services import get_session_for_user, mark_all_present

    try:
        session = await _run_db(get_session_for_user, user, session_id)
        await _run_db(mark_all_present, session, actor=user)
    except PermissionDenied:
        await send_reply(update, "Bu davomat darsi sizga tegishli emas.")
        return
    await _render_attendance(update, context, session)


async def _finalize_attendance(
    update: Update, context, user, session_id: int, mark_unmarked_absent: bool = False
) -> None:
    """Finalize a register, refusing to invent absences without confirmation."""
    from apps.attendance.services import (
        AttendanceError,
        finalize_and_notify,
        get_session_for_user,
    )

    try:
        session = await _run_db(get_session_for_user, user, session_id)
        result = await _run_db(
            lambda: finalize_and_notify(
                session,
                actor=user,
                mark_unmarked_as_absent=mark_unmarked_absent,
                reason="Bot orqali yakunlandi",
            )
        )
    except AttendanceError as exc:
        await send_reply(update, exc.messages[0] if exc.messages else "Xatolik.")
        return
    except PermissionDenied:
        await send_reply(update, "Bu davomat darsi sizga tegishli emas.")
        return

    if not result.get("ok"):
        # Never silently classify an unmarked student as absent.
        unmarked = result.get("unmarked", [])
        names = ", ".join(entry["name"] for entry in unmarked[:20])
        await edit_or_reply(
            update,
            "⚠️ *Davomat yakunlanmadi*\n\n"
            f"Belgilanmagan o'quvchilar ({len(unmarked)}):\n{names}\n\n"
            "Avval ularni belgilang yoki ularni kelmadi deb tasdiqlang.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Belgilanmaganlarni kelmadi deb belgilash",
                            callback_data=f"tfinabs_{session.id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "Orqaga",
                            callback_data=f"tatt_{session.group_id}",
                        )
                    ],
                ]
            ),
        )
        return

    text = (
        f"✅ *{result['group_name']} — Davomat yakunlandi*\n\n"
        f"🗓 {result['lesson_date']} {result['time_label']}\n"
        f"👥 {result['roster_size']} o'quvchi:\n"
        f"• ✅ {result['present']} keldi\n"
        f"• ⏰ {result['late']} kechikdi\n"
        f"• 📄 {result['excused']} sababli\n"
        f"• ❌ {result['absent']} kelmadi"
    )

    # Kelmagan o'quvchilar ota-onalariga ogohlantirish yuborish
    def _notify_absences(sess):
        from apps.notifications.tasks_parent import send_parent_absence_alert_task

        absent_recs = sess.records.filter(status="absent")
        for rec in absent_recs:
            try:
                send_parent_absence_alert_task.delay(sess.id, rec.student_id)
            except Exception:
                pass

    await _run_db(_notify_absences, session)

    await edit_or_reply(
        update,
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📊 Hisobot", callback_data=f"trpt_{session.group_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏠 Guruh", callback_data=f"tgrp_{session.group_id}"
                    )
                ],
            ]
        ),
    )


@require_role("TEACHER")
async def attendance_report_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/attendance_report — choose a group for attendance statistics."""
    user = await _teacher_from_update(update)
    if not user:
        return
    from apps.attendance.services import teacher_groups

    groups = await _run_db(lambda: list(teacher_groups(user).order_by("name")))
    if not groups:
        await send_reply(update, "🏫 Sizga guruh biriktirilmagan.")
        return
    await send_reply(
        update,
        "📊 *Qaysi guruh hisoboti kerak?*",
        parse_mode="Markdown",
        reply_markup=_group_list_keyboard(groups, callback_prefix="trpt_"),
    )


async def _send_attendance_report(
    update: Update, context, user, group, days: int | None
) -> None:
    from apps.attendance.services import group_attendance_report

    if days:
        from datetime import timedelta

        from django.utils import timezone

        end = timezone.localdate()
        start = end - timedelta(days=days)
        report = await _run_db(
            lambda: group_attendance_report(group, start=start, end=end)
        )
    else:
        report = await _run_db(group_attendance_report, group)

    percentage = (
        f"{report['attendance_percentage']}%"
        if report["attendance_percentage"] is not None
        else "—"
    )
    text = (
        f"📊 *{report['group_name']} — davomat hisoboti*\n"
        f"_{report['start']} — {report['end']}_\n\n"
        f"👥 O'quvchilar: *{report['roster_size']}*\n"
        f"🗓 Darslar: *{report['finalized_sessions']}* yakunlangan"
        + (
            f", {report['pending_sessions']} yakunlanmagan\n"
            if report["pending_sessions"]
            else "\n"
        )
        + f"📈 Davomat: *{percentage}*\n\n"
        f"✅ Keldi: *{report['present']}*\n"
        f"⏰ Kechikdi: *{report['late']}*\n"
        f"📄 Sababli: *{report['excused']}*\n"
        f"❌ Kelmadi (sababsiz): *{report['unexcused_absent']}*\n\n"
        "_Yakunlanmagan davomat darslari kelmaganlik deb hisoblanmaydi._"
    )
    await edit_or_reply(
        update,
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🗓 Haftalik", callback_data=f"trptw_{group.id}")],
                [InlineKeyboardButton("🗓 Oylik", callback_data=f"trptm_{group.id}")],
                [InlineKeyboardButton("🏠 Guruh", callback_data=f"tgrp_{group.id}")],
            ]
        ),
    )


@require_role("TEACHER")
async def students_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/students — choose a group to list its students."""
    user = await _teacher_from_update(update)
    if not user:
        return
    from apps.attendance.services import teacher_groups

    groups = await _run_db(lambda: list(teacher_groups(user).order_by("name")))
    if not groups:
        await send_reply(update, "🏫 Sizga guruh biriktirilmagan.")
        return
    await send_reply(
        update,
        "👥 *Qaysi guruh o'quvchilari?*",
        parse_mode="Markdown",
        reply_markup=_group_list_keyboard(groups, callback_prefix="tstu_"),
    )


async def _send_students(update: Update, context, user, group) -> None:
    from apps.courses.group_service import get_group_full_analytics

    analytics = await _run_db(get_group_full_analytics, group)
    roster = analytics.get("students") or analytics.get("roster") or []
    invite_code = getattr(group, "invite_code", "") or f"GR-{group.id}"
    if not roster:
        await edit_or_reply(
            update,
            f"🏫 *{group.name}* guruhida hozircha o'quvchilar yo'q.\n\n"
            f"Taklif kodi: `#{invite_code}`\n"
            f"O'quvchilar ushbu kodni botga yozishi bilan bu yerda paydo bo'ladi.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🏠 Guruh", callback_data=f"tgrp_{group.id}"
                        ),
                    ]
                ]
            ),
        )
        return

    group_avg = analytics.get("group_avg_percentage", analytics.get("group_avg_pct", 0))
    lines = [
        f"👥 *{group.name} — O'quvchilar va BMB Monitoringi*",
        f"Jami a'zolar: *{len(roster)} nafar* · Guruh o'rtacha: *{group_avg}%*\n",
    ]
    for index, s in enumerate(roster, 1):
        name = (
            s.get("student_name") or s.get("full_name") or s.get("name") or "O'quvchi"
        )
        tests_count = s.get("tests_count", s.get("tests_taken", 0))
        avg_test_pct = s.get("avg_test_percentage", s.get("avg_test_pct", 0.0))
        bmb_grade = s.get("latest_test_grade") or s.get("bmb_grade") or "—"
        essays_count = s.get("essays_count", s.get("essays_written", 0))
        latest_essay = s.get("latest_essay_score", s.get("avg_essay_score", "—"))
        attendance_str = s.get("attendance_pct") or s.get("attendance") or "100%"
        lines.append(
            f"*{index}. {name}* ({s.get('pro_status_label', s.get('plan_badge', 'PRO'))})\n"
            f"   📊 Testlar: *{tests_count} ta* (O'rtacha: *{avg_test_pct}%*) · BMB: *{bmb_grade}*\n"
            f"   📝 Esselar: *{essays_count} ta* (Oxirgi ball: *{latest_essay}*)\n"
            f"   🗓 davomat: *{attendance_str}*\n"
        )

    bmb_summary = analytics.get("bmb_counts", {})
    bmb_line = " · ".join(f"*{k}:* {v}" for k, v in bmb_summary.items() if v > 0)
    if bmb_line:
        lines.append(f"🏆 *BMB Taqsimoti:* {bmb_line}")

    await edit_or_reply(
        update,
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📊 Excel hisobot (.xlsx)", callback_data=f"texcel_{group.id}"
                    ),
                    InlineKeyboardButton(
                        "💳 To'lov holati", callback_data=f"ttuition_{group.id}"
                    ),
                ],
                [InlineKeyboardButton("🏠 Guruh", callback_data=f"tgrp_{group.id}")],
            ]
        ),
    )


@require_role("TEACHER")
async def essay_results_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/essay_results — choose a group for its essay results."""
    user = await _teacher_from_update(update)
    if not user:
        return
    from apps.essays.group_reports import teacher_groups

    groups = await _run_db(lambda: list(teacher_groups(user).order_by("name")))
    if not groups:
        await send_reply(update, "🏫 Sizga guruh biriktirilmagan.")
        return
    await send_reply(
        update,
        "📝 *Qaysi guruh esse natijalari?*",
        parse_mode="Markdown",
        reply_markup=_group_list_keyboard(groups, callback_prefix="ters_"),
    )


async def _send_essay_results(
    update: Update, context, user, group, *, state: str | None = None, offset: int = 0
) -> None:
    """Page of essay result rows. Aggregate header, never a full essay dump."""
    from apps.essays.group_reports import group_essay_results, group_essay_summary

    summary = await _run_db(group_essay_summary, group)
    data = await _run_db(
        lambda: group_essay_results(
            group,
            state=state,
            limit=_ESSAY_PAGE_SIZE,
            offset=offset,
        )
    )

    header = (
        f"📝 *{group.name} — Esse natijalari*\n\n"
        f"✅ Baholangan: *{summary['graded']}*\n"
        f"⏳ Kutilmoqda: *{summary['pending']}*\n"
        f"📭 Topshirilmagan: *{summary['not_submitted']}*"
    )
    if summary.get("average_ai_score") is not None:
        header += f"\n📈 O'rtacha AI ball: *{summary['average_ai_score']}*"

    lines = [header, ""]
    if not data["results"]:
        lines.append("Bu filtr bo'yicha natija yo'q.")
    for row in data["results"]:
        score = (
            f"{row['effective_score']}/{row['max_score']}"
            if row["effective_score"] is not None
            else "—"
        )
        lines.append(
            f"• *{row['student_name']}* — {row['topic_title']}\n"
            f"  {row['source_label']} · {row['status_label']} · {score}"
        )
        if row["teacher_review_required"]:
            lines.append("  ⚠️ O'qituvchi tekshiruvi kerak")
    lines.append("")
    lines.append(f"_Ko'rsatilgan: {data['shown']} / {data['total']}_")

    keyboard_rows = [
        # Link to the authenticated panel (the same route the main menu uses)
        # rather than dumping essays and detailed feedback into the chat.
        [InlineKeyboardButton("📋 To'liq hisobot", url=f"{_site_url()}/dashboard/")],
        [
            InlineKeyboardButton(
                "⏳ Baholanmaganlar", callback_data=f"terspend_{group.id}"
            )
        ],
    ]
    nav = []
    if offset > 0:
        nav.append(
            InlineKeyboardButton(
                "⬅️ Oldingi",
                callback_data=f"tersp_{group.id}_{max(0, offset - _ESSAY_PAGE_SIZE)}",
            )
        )
    if offset + _ESSAY_PAGE_SIZE < data["total"]:
        nav.append(
            InlineKeyboardButton(
                "➡️ Keyingi",
                callback_data=f"tersp_{group.id}_{offset + _ESSAY_PAGE_SIZE}",
            )
        )
    if nav:
        keyboard_rows.append(nav)
    keyboard_rows.append(
        [InlineKeyboardButton("🏠 Guruh", callback_data=f"tgrp_{group.id}")]
    )
    await edit_or_reply(
        update,
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )


@require_role("TEACHER")
async def group_report_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/group_report — choose a group for a combined performance report."""
    user = await _teacher_from_update(update)
    if not user:
        return
    from apps.essays.group_reports import teacher_groups

    groups = await _run_db(lambda: list(teacher_groups(user).order_by("name")))
    if not groups:
        await send_reply(update, "🏫 Sizga guruh biriktirilmagan.")
        return
    await send_reply(
        update,
        "📈 *Qaysi guruh hisoboti?*",
        parse_mode="Markdown",
        reply_markup=_group_list_keyboard(groups, callback_prefix="tgreport_"),
    )


async def _send_group_report(update: Update, context, user, group) -> None:
    from apps.attendance.services import group_attendance_report
    from apps.essays.group_reports import group_essay_summary, overdue_assignments

    attendance = await _run_db(group_attendance_report, group)
    essays = await _run_db(group_essay_summary, group)
    overdue = await _run_db(overdue_assignments, user)
    overdue = [row for row in overdue if row["group_name"] == group.name]
    percentage = (
        f"{attendance['attendance_percentage']}%"
        if attendance["attendance_percentage"] is not None
        else "—"
    )
    text = (
        f"📈 *{group.name} — guruh hisoboti*\n"
        f"_{attendance['start']} — {attendance['end']}_\n\n"
        f"👥 O'quvchilar: *{attendance['roster_size']}*\n"
        f"📊 Davomat: *{percentage}* ({attendance['finalized_sessions']} dars)"
        + (
            f" · yakunlanmagan: {attendance['pending_sessions']}"
            if attendance["pending_sessions"]
            else ""
        )
        + "\n\n"
        f"📝 *Esse*\n"
        f"✅ Baholangan: *{essays['graded']}*\n"
        f"⏳ Kutilmoqda: *{essays['pending']}*\n"
        f"⚠️ Xatolik: *{essays['failed']}*\n"
        f"📭 Topshirilmagan: *{essays['not_submitted']}*"
    )
    if essays.get("average_ai_score") is not None:
        text += f"\n📈 O'rtacha AI ball: *{essays['average_ai_score']}*"
    if overdue:
        text += "\n\n⏰ *Muddati o'tgan topshiriqlar*\n"
        for row in overdue[:5]:
            text += f"• {row['topic_title']} — {row['not_submitted']} topshirilmagan\n"
    await edit_or_reply(
        update,
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📊 Davomat hisoboti", callback_data=f"trpt_{group.id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📝 Esse natijalari", callback_data=f"ters_{group.id}"
                    )
                ],
                [InlineKeyboardButton("🏠 Guruh", callback_data=f"tgrp_{group.id}")],
            ]
        ),
    )


def _parse_mark_callback(data: str) -> tuple[int, int, str] | None:
    """Parse ``tmk_<session_id>_<student_id>_<status>``.

    The status is a word, not an integer, so the generic integer parser cannot
    be reused. A malformed payload returns ``None`` instead of raising.
    """
    from apps.attendance.models import AttendanceRecord

    parts = data[len("tmk_") :].split("_")
    if len(parts) != 3:
        logger.warning("Malformed attendance callback: %r", data)
        return None
    session_raw, student_raw, status = parts
    try:
        session_id, student_id = int(session_raw), int(student_raw)
    except (TypeError, ValueError):
        logger.warning("Malformed attendance callback: %r", data)
        return None
    if status not in dict(AttendanceRecord.Status.choices):
        logger.warning("Unknown attendance status in callback: %r", data)
        return None
    return session_id, student_id, status


async def _group_card_callback(update: Update, context, group_id: int) -> None:
    user = await _teacher_from_update(update)
    if not user:
        return
    group = await _load_managed_group(user, group_id)
    if group is None:
        await edit_or_reply(update, "🏫 Guruh topilmadi yoki sizga tegishli emas.")
        return
    await _send_group_card(update, context, user, group)


async def _attendance_callback(update: Update, context, group_id: int) -> None:
    user = await _teacher_from_update(update)
    if not user:
        return
    group = await _load_managed_group(user, group_id)
    if group is None:
        await edit_or_reply(update, "🏫 Guruh topilmadi yoki sizga tegishli emas.")
        return
    await _start_attendance(update, context, user, group)


async def _mark_callback(
    update: Update, context, session_id: int, student_id: int, status: str
) -> None:
    user = await _teacher_from_update(update)
    if not user:
        return
    await _mark_student(update, context, user, session_id, student_id, status)


async def _all_present_callback(update: Update, context, session_id: int) -> None:
    user = await _teacher_from_update(update)
    if not user:
        return
    await _mark_all_present(update, context, user, session_id)


async def _finalize_callback(
    update: Update, context, session_id: int, mark_unmarked_absent: bool = False
) -> None:
    user = await _teacher_from_update(update)
    if not user:
        return
    await _finalize_attendance(
        update,
        context,
        user,
        session_id,
        mark_unmarked_absent=mark_unmarked_absent,
    )


async def _attendance_report_callback(
    update: Update, context, group_id: int, days: int | None = None
) -> None:
    user = await _teacher_from_update(update)
    if not user:
        return
    group = await _load_managed_group(user, group_id)
    if group is None:
        await edit_or_reply(update, "🏫 Guruh topilmadi yoki sizga tegishli emas.")
        return
    await _send_attendance_report(update, context, user, group, days)


async def _students_callback(update: Update, context, group_id: int) -> None:
    user = await _teacher_from_update(update)
    if not user:
        return
    group = await _load_managed_group(user, group_id)
    if group is None:
        await edit_or_reply(update, "🏫 Guruh topilmadi yoki sizga tegishli emas.")
        return
    await _send_students(update, context, user, group)


async def _essay_results_callback(
    update: Update, context, group_id: int, *, state: str | None = None, offset: int = 0
) -> None:
    user = await _teacher_from_update(update)
    if not user:
        return
    group = await _load_managed_group(user, group_id)
    if group is None:
        await edit_or_reply(update, "🏫 Guruh topilmadi yoki sizga tegishli emas.")
        return
    await _send_essay_results(update, context, user, group, state=state, offset=offset)


async def _group_report_callback(update: Update, context, group_id: int) -> None:
    user = await _teacher_from_update(update)
    if not user:
        return
    group = await _load_managed_group(user, group_id)
    if group is None:
        await edit_or_reply(update, "🏫 Guruh topilmadi yoki sizga tegishli emas.")
        return
    await _send_group_report(update, context, user, group)


async def _weekly_report_detail_callback(
    update: Update, context, report_id: int, section: str
) -> None:
    """Show a private section of a stored weekly report to its authorized teacher."""
    from apps.accounts.access import is_platform_admin
    from apps.weekly_reports import delivery as report_delivery
    from apps.weekly_reports.models import WeeklyGroupReport

    user = await _get_or_create_user_async(update)
    if not user or not await _run_db(_is_teacher_account, user):
        await edit_or_reply(update, "Bu hisobotni ko'rish huquqingiz yo'q.")
        return

    report = await _run_db(
        lambda: (
            WeeklyGroupReport.objects.filter(pk=report_id)
            .select_related("group")
            .first()
        ),
    )
    if report is None or not await _run_db(
        lambda: is_platform_admin(user) or report.group.teacher_id == user.pk,
    ):
        await edit_or_reply(update, "Hisobot topilmadi yoki sizga tegishli emas.")
        return

    summary = report.summary or {}
    include_finance = await _run_db(report_delivery._may_see_finance, user)
    if section == "wr_fin_":
        if not include_finance:
            await edit_or_reply(update, "Kurs to'lovlarini ko'rish huquqingiz yo'q.")
            return
        visible = {"finance": summary.get("finance")}
        title = "💳 Kurs to'lovlari"
        labels = {
            "policy_configured": "Siyosat sozlangan",
            "period_invoices": "Hisob-fakturalar",
            "paid_count": "To'langan o'quvchilar",
            "partial_count": "Qisman to'langan o'quvchilar",
            "unpaid_count": "To'lanmagan o'quvchilar",
            "overdue_count": "Muddati o'tgan o'quvchilar",
            "billed_uzs": "Hisoblangan summa (so'm)",
            "confirmed_paid_uzs": "Tasdiqlangan to'lovlar (so'm)",
            "outstanding_uzs": "Qoldiq (so'm)",
        }
        block = visible.get("finance") or {}
        lines = [
            title,
            "",
            f"Guruh: {report.group.name}",
            f"Davr: {report.period_label}",
        ]
        lines.extend(f"{label}: {block.get(key, '—')}" for key, label in labels.items())
    else:
        title_map = {
            "wr_att_": ("📋 Davomat tafsilotlari", "attendance"),
            "wr_ess_": ("📝 Esse natijalari", "essays"),
            "wr_tst_": ("🧪 Test natijalari", "tests"),
        }
        if section == "wr_full_":
            title = "📄 Haftalik to'liq hisobot"
            block_keys = ("attendance", "essays", "tests")
            if include_finance and summary.get("finance") is not None:
                block_keys += ("finance",)
        elif section in title_map:
            title, block = title_map[section]
            block_keys = (block,)
        else:
            await edit_or_reply(update, "Hisobot bo'limi topilmadi.")
            return
        lines = [
            title,
            "",
            f"Guruh: {report.group.name}",
            f"Davr: {report.period_label}",
        ]
        for key in block_keys:
            block = summary.get(key)
            if block is not None:
                lines.extend(["", _weekly_section_text(key, block)])
    await edit_or_reply(
        update,
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔙 Asosiy hisobot", callback_data=f"wr_full_{report.pk}"
                    ),
                    InlineKeyboardButton(
                        "🏠 Guruh", callback_data=f"tgrp_{report.group_id}"
                    ),
                ]
            ]
        ),
    )


def _weekly_section_text(section: str, values: dict) -> str:
    """Render persisted aggregate values without any student identifiers."""
    titles = {
        "attendance": "📋 Davomat",
        "essays": "📝 Esse natijalari",
        "tests": "🧪 Test natijalari",
        "finance": "💳 Kurs to'lovlari",
    }
    lines = [titles.get(section, section)]
    labels = {
        "attendance": {
            "active_students": "Faol o'quvchilar",
            "finalized_lessons": "Yakunlangan darslar",
            "unfinished_lessons": "Yakunlanmagan darslar",
            "present": "Keldi",
            "late": "Kechikdi",
            "excused_absences": "Sababli yo'qlik",
            "unexcused_absences": "Sababsiz yo'qlik",
            "attendance_percentage": "Davomat foizi",
            "follow_up_count": "Davomat bo'yicha kuzatuv",
        },
        "essays": {
            "assigned_essays": "Biriktirilgan esselar",
            "expected_submissions": "Kutilayotgan topshiriqlar",
            "submitted_students": "Topshirgan o'quvchilar",
            "missing_submissions": "Topshirilmagan",
            "graded": "Baholangan",
            "pending_ai": "AI baholash kutilmoqda",
            "teacher_reviewed": "O'qituvchi tekshirgan",
            "grading_failed": "Baholash xatosi",
            "average_raw_score": "O'rtacha xom ball",
            "score_distribution": "Ball taqsimoti",
        },
        "tests": {
            "assigned_tests": "Biriktirilgan testlar",
            "completed_attempts": "Yakunlangan urinishlar",
            "incomplete_attempts": "Yakunlanmagan urinishlar",
            "pending_grading": "Baholash kutilmoqda",
            "average_practice_percentage": "O'rtacha mashq foizi",
            "needs_support_count": "Qo'shimcha yordam kerak",
        },
        "finance": {
            "policy_configured": "Siyosat sozlangan",
            "paid_count": "To'langan o'quvchilar",
            "partial_count": "Qisman to'langan o'quvchilar",
            "unpaid_count": "To'lanmagan o'quvchilar",
            "overdue_count": "Muddati o'tgan o'quvchilar",
            "billed_uzs": "Hisoblangan so'm",
            "confirmed_paid_uzs": "Tasdiqlangan so'm",
            "outstanding_uzs": "Qoldiq so'm",
        },
    }
    for key, label in labels.get(section, {}).items():
        value = values.get(key)
        if value is not None:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def _safe_report_callback_id(data: str) -> int | None:
    for prefix in ("wr_att_", "wr_ess_", "wr_tst_", "wr_fin_", "wr_full_"):
        if data.startswith(prefix):
            raw = data[len(prefix) :]
            if raw.isdecimal():
                return int(raw)
            logger.warning("Malformed weekly report callback: %r", data)
            return None
    return None


# ---------------------------------------------------------------------------
# Safe parsing of callback payloads
# ---------------------------------------------------------------------------


def _safe_callback_int(data: str, prefix: str) -> int | None:
    """Parse an integer from a callback string, tolerating malformed payloads."""
    raw = data[len(prefix) :] if data.startswith(prefix) else data
    try:
        return int(raw)
    except (ValueError, TypeError):
        logger.warning("Malformed callback payload: %r", data)
        return None


# ---------------------------------------------------------------------------
# 👨‍👩‍👧 Ota-onalar nazorati & 🏆 Turnir Handlers
# ---------------------------------------------------------------------------


async def parent_start_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /parent_start or /parent — Parent registration and smart alerts linking."""
    tg_user = update.effective_user
    if not tg_user:
        return

    args = context.args if context.args else []
    code = args[0].strip() if args else ""
    if code.startswith("parent_"):
        code = code.removeprefix("parent_")

    def _link_by_code(code_val: str, chat_id: int):
        from apps.accounts.models import ParentStudentRelation

        rel = (
            ParentStudentRelation.objects.filter(verification_code=code_val)
            .select_related("student")
            .first()
        )
        if not rel:
            return None
        rel.parent_telegram_id = chat_id
        rel.is_verified = True
        rel.save(update_fields=["parent_telegram_id", "is_verified", "updated_at"])
        return rel.student.get_full_name() or rel.student.email

    if code:
        student_name = await _run_db(_link_by_code, code, tg_user.id)
        if student_name:
            await update.message.reply_text(
                f"✅ <b>Muvaffaqiyatli bog'landi!</b>\n\n"
                f"Siz o'quvchi <b>{student_name}</b> ga ota-ona sifatida biriktirildingiz.\n\n"
                f"Endi farzandingizning:\n"
                f"• Mock va test natijalari (ball, foiz, BMB darajasi)\n"
                f"• Esse baholari\n"
                f"• Har yakshanba 18:00 dagi haftalik o'sish hisoboti\n"
                f"to'g'ridan-to'g'ri ushbu chatga avtomatik yuboriladi.",
                parse_mode="HTML",
            )
            return
        else:
            await update.message.reply_text(
                "❌ Tasdiqlash kodi noto'g'ri yoki eskirgan. Farzandingizdan yangi kod olishini so'rang.",
                parse_mode="HTML",
            )
            return

    # Check if this telegram user already has linked students
    def _get_linked_students(chat_id: int):
        from apps.accounts.models import ParentStudentRelation

        rels = list(
            ParentStudentRelation.objects.filter(
                parent_telegram_id=chat_id, is_verified=True
            ).select_related("student")
        )
        return [r.student.get_full_name() or r.student.email for r in rels]

    linked = await _run_db(_get_linked_students, tg_user.id)
    if linked:
        names_str = "\n".join(f"• <b>{n}</b>" for n in linked)
        msg_text = (
            f"👨‍👩‍👧 <b>OTA-ONALAR NAZORATI TIZIMI</b>\n\n"
            f"Sizga quyidagi o'quvchilar biriktirilgan:\n{names_str}\n\n"
            f"🔔 Tezkor xabarnomalar va haftalik hisobotlar faol.\n"
            f"Yangi o'quvchini ulash uchun: <code>/parent_start KOD</code>"
        )
        if update.callback_query:
            await update.callback_query.message.reply_text(msg_text, parse_mode="HTML")
        else:
            await update.message.reply_text(msg_text, parse_mode="HTML")
        return

    context.user_data["awaiting_parent_code"] = True
    welcome_msg = (
        "👨‍👩‍👧 <b>OTA-ONALAR NAZORATI TIZIMIGA XUSH KELIBSIZ!</b>\n\n"
        "Farzandingizning test natijalari, BMB darajalari va davomatini ushbu Telegram bot orqali kuzatib boring.\n\n"
        "📌 <b>Ulanish uchun:</b>\n"
        "1. Farzandingiz veb-saytda yoki botda <code>/parent_link</code> orqali olingan <b>6 xonali kod</b>ni bu yerga yuboring.\n"
        "Masalan: <code>123456</code> yoki <code>/parent_start 123456</code>\n"
        "2. Yoki pastdagi tugma orqali telefon raqamingizni yuboring."
    )
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)],
            [KeyboardButton("🔙 Asosiy menyu")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    if update.callback_query:
        await update.callback_query.message.reply_text(
            welcome_msg, parse_mode="HTML", reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            welcome_msg, parse_mode="HTML", reply_markup=keyboard
        )


async def parent_link_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /parent_link <phone> — Student initiates linking parent phone."""
    args = context.args if context.args else []
    user = await _get_or_create_user_async(update)
    if not user:
        await update.message.reply_text("Xatolik: foydalanuvchi topilmadi.")
        return

    if not args:
        await update.message.reply_text(
            "👨‍👩‍👧 <b>Ota-ona raqamini ulash</b>\n\n"
            "Ota-onangiz telefon raqamini quyidagicha yuboring:\n"
            "<code>/parent_link +998901234567</code>\n\n"
            "Tizim sizga 6 xonali tasdiqlash kodini beradi. Ota-onangiz ushbu botga kirib, "
            "kodni kiritishi bilan natijalaringiz ularga boradi.",
            parse_mode="HTML",
        )
        return

    raw_phone = args[0].strip()
    import re

    digits = re.sub(r"\D", "", raw_phone)
    if len(digits) < 9:
        await update.message.reply_text(
            "Telefon raqami noto'g'ri. Masalan: <code>/parent_link +998901234567</code>",
            parse_mode="HTML",
        )
        return

    clean_phone = "+998" + digits[-9:]

    def _create_relation(student_user, phone: str):
        import random
        from apps.accounts.models import ParentStudentRelation

        code_val = f"{random.randint(100000, 999999)}"
        rel, _ = ParentStudentRelation.objects.get_or_create(
            student=student_user,
            parent_phone=phone,
            defaults={
                "verification_code": code_val,
                "weekly_report_enabled": True,
                "instant_alerts_enabled": True,
            },
        )
        if not rel.is_verified:
            rel.verification_code = code_val
            rel.save(update_fields=["verification_code"])
        return rel.verification_code

    code = await _run_db(_create_relation, user, clean_phone)
    await update.message.reply_text(
        f"✅ <b>Ota-ona raqami saqlandi:</b> <code>{clean_phone}</code>\n\n"
        f"🔑 <b>Tasdiqlash kodi:</b> <code>{code}</code>\n\n"
        f"Ota-onangizga ushbu xabarni yuboring:\n"
        f"<i>«Botga kiring va <code>/parent_start {code}</code> deb yuboring!»</i>",
        parse_mode="HTML",
    )


async def tournament_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /tournament — Sunday Live League info and quick entry."""
    from django.conf import settings as _settings

    site_url = getattr(_settings, "SITE_URL", "https://grandec.uz").rstrip("/")

    def _get_tournaments():
        from apps.arena.models import Tournament

        t = (
            Tournament.objects.filter(status__in=["upcoming", "live"])
            .order_by("scheduled_at")
            .first()
        )
        if not t:
            t = Tournament.objects.order_by("-scheduled_at").first()
        if not t:
            return None
        return {
            "id": t.id,
            "title": t.title,
            "scheduled_at": t.scheduled_at.strftime("%d.%m.%Y soat %H:%M"),
            "duration": t.duration_minutes,
            "status": t.status,
            "prizes": t.prize_fund_description,
            "participants": t.participants.count(),
        }

    t_data = await _run_db(_get_tournaments)
    if not t_data:
        msg_none = "Hozircha faol turnirlar mavjud emas. Tez kunda yangi Yakshanba turniri e'lon qilinadi!"
        if update.callback_query:
            await update.callback_query.message.reply_text(msg_none)
        else:
            await update.message.reply_text(msg_none)
        return

    status_badge = (
        "🔴 HOZIR JONLI!" if t_data["status"] == "live" else "⏳ YAQINLASHMOQDA"
    )

    msg = (
        f"🏆 <b>JONLI YAKSHANBA TURNIRI (SUNDAY LIVE LEAGUE)</b>\n\n"
        f"📌 <b>Turnir:</b> {t_data['title']}\n"
        f"📊 <b>Holati:</b> {status_badge}\n"
        f"📅 <b>Boshlanish vaqti:</b> {t_data['scheduled_at']}\n"
        f"⏱ <b>Davomiyligi:</b> {t_data['duration']} daqiqa\n"
        f"👥 <b>Qatnashuvchilar:</b> {t_data['participants']} nafar\n\n"
        f"🎁 <b>MUKOFOTLAR:</b>\n"
        f"{t_data['prizes']}\n\n"
        f"Turnirda barcha o'quvchilar bir vaqtda start oladi va jonli reyting animatsiya bilan har soniyada yangilanib turadi!"
    )

    t_url = f"{site_url}/tournaments/{t_data['id']}/live"
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🚀 Turnirga kirish (Live)", url=t_url)],
            [InlineKeyboardButton("📊 ELO Reyting", callback_data="menu_leaderboard")],
        ]
    )

    if update.callback_query:
        await update.callback_query.message.reply_text(
            msg, parse_mode="HTML", reply_markup=keyboard
        )
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=keyboard)


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------


def setup_handlers(app) -> None:
    """Register all handlers with the Application."""
    from telegram.ext import (
        CallbackQueryHandler,
        CommandHandler,
        MessageHandler,
        filters,
    )

    # Global error handler — a crash in one handler must never kill the bot
    app.add_error_handler(error_handler)

    # Commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("profile", profile_handler))
    app.add_handler(CommandHandler("tests", tests_handler))
    app.add_handler(CommandHandler("results", results_handler))
    app.add_handler(CommandHandler("essays", essays_handler))
    app.add_handler(CommandHandler("essay_submit", essay_submit_handler))
    app.add_handler(CommandHandler("cancel_essay", cancel_essay_handler))
    app.add_handler(CommandHandler("leaderboard", leaderboard_handler))
    app.add_handler(CommandHandler("streak", streak_handler))
    app.add_handler(CommandHandler("daily", daily_handler))
    app.add_handler(CommandHandler("premium", premium_handler))
    app.add_handler(CommandHandler("parent_start", parent_start_handler))
    app.add_handler(CommandHandler("parent_link", parent_link_handler))
    app.add_handler(CommandHandler("parent", parent_start_handler))
    app.add_handler(CommandHandler("tournament", tournament_handler))
    app.add_handler(CommandHandler("tournaments", tournament_handler))
    # Teacher group management, mock creation, attendance and group reports
    app.add_handler(CommandHandler("newmock", newmock_handler))
    app.add_handler(CommandHandler("admin", admin_panel_handler))
    app.add_handler(CommandHandler("groups", groups_handler))
    app.add_handler(CommandHandler("my_groups", groups_handler))
    app.add_handler(CommandHandler("create_group", create_group_handler))
    app.add_handler(CommandHandler("export_group_report", export_group_report_handler))
    app.add_handler(CommandHandler("group_leaderboard", group_leaderboard_handler))
    app.add_handler(CommandHandler("new_homework", new_homework_handler))
    app.add_handler(CommandHandler("attendance", attendance_handler))
    app.add_handler(CommandHandler("attendance_report", attendance_report_handler))
    app.add_handler(CommandHandler("students", students_handler))
    app.add_handler(CommandHandler("essay_results", essay_results_handler))
    app.add_handler(CommandHandler("group_report", group_report_handler))
    app.add_handler(CommandHandler("plans", plans_handler))
    app.add_handler(CommandHandler("buy", buy_handler))
    app.add_handler(CommandHandler("myplan", myplan_handler))
    app.add_handler(CommandHandler("mytuition", mytuition_handler))
    app.add_handler(CommandHandler("course_payment", course_payment_handler))
    app.add_handler(CommandHandler("payment_history", payment_history_handler))
    app.add_handler(CommandHandler("payment_proof", payment_proof_handler))
    app.add_handler(CommandHandler("weekly_report", weekly_report_handler))
    app.add_handler(CommandHandler("group_payments", group_payments_handler))
    app.add_handler(CommandHandler("limits", limits_handler))
    app.add_handler(CommandHandler("paysupport", paysupport_handler))
    app.add_handler(CommandHandler("cancel", cancel_handler))
    app.add_handler(CommandHandler("essay", essay_handler))
    app.add_handler(CommandHandler("arena", arena_handler))
    app.add_handler(CommandHandler("arena_join", arena_join_handler))
    app.add_handler(CommandHandler("certificates", certificates_handler))
    app.add_handler(CommandHandler("myattendance", myattendance_handler))

    # Telegram Stars payments — registered before the generic message handlers
    # so a paid update can never be swallowed by the text/photo routers.
    from telegram.ext import PreCheckoutQueryHandler

    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler)
    )

    # Essay page images. A lower group keeps the payment-screenshot handler
    # working: each handler no-ops when its own flow is not active.
    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.Document.ALL,
            essay_image_message_handler,
        ),
        group=-1,
    )

    # Arena callbacks (must be before generic callback_handler)
    app.add_handler(
        CallbackQueryHandler(arena_callback_handler, pattern=r"^(arena_|ar_)")
    )

    # Quiz handler (must be before generic callback_handler)
    from apps.notifications.bot.quiz import quiz_handler, quiz_callback_handler

    app.add_handler(CommandHandler("quiz", quiz_handler))
    app.add_handler(CommandHandler("finance", finance_handler))
    app.add_handler(CommandHandler("vocab", vocab_handler))
    app.add_handler(CallbackQueryHandler(quiz_callback_handler, pattern=r"^quiz_"))

    # Auth conversation handler — catches text/contact during auth flow
    # Must be before generic callback_handler but after command handlers
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, auth_conversation_handler)
    )
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
            "429",
            "too many requests",
            "bot was blocked",
            "forbidden: bot was blocked",
            "chat not found",
            "user is deactivated",
        )
    ):
        logger.warning(
            "Bot API error (non-fatal): %s (update=%s)",
            error,
            getattr(update, "update_id", "?"),
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
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Botni ishga tushirish"),
            BotCommand("help", "Yordam"),
            BotCommand("quiz", "🧠 Telegram Quiz — test topshirish"),
            BotCommand("results", "Barcha natijalar"),
            BotCommand("profile", "Shaxsiy profil"),
            BotCommand("tests", "Mavjud testlar"),
            BotCommand("essays", "Esse mavzulari"),
            BotCommand("essay_submit", "Esseni botda topshirish"),
            BotCommand("cancel_essay", "Esse yuborishni bekor qilish"),
            BotCommand("leaderboard", "Reyting"),
            BotCommand("streak", "Kunlik streak"),
            BotCommand("daily", "Kunlik vazifalar"),
            BotCommand("essay", "Esse topshirish (matn/rasm)"),
            BotCommand("certificates", "📜 Rasmiy PDF sertifikatlar"),
            BotCommand("plans", "Tariflar va narxlar"),
            BotCommand("buy", "Tarif sotib olish (Telegram Stars)"),
            BotCommand("myplan", "Mening platforma tarifim"),
            BotCommand("mytuition", "Kurs to'lovlari"),
            BotCommand("myattendance", "📅 Mening davomatim"),
            BotCommand("course_payment", "Mening to'lov holatim"),
            BotCommand("payment_history", "To'lovlar tarixi"),
            BotCommand("payment_proof", "To'lov dalilini yuborish"),
            BotCommand("weekly_report", "Haftalik guruh hisobotlari"),
            BotCommand("group_payments", "Guruh bo'yicha jami to'lovlar"),
            BotCommand("limits", "Qolgan limitingiz"),
            BotCommand("paysupport", "To'lov bo'yicha yordam"),
            BotCommand("cancel", "Joriy amalni bekor qilish"),
            BotCommand("premium", "Premium obuna"),
            BotCommand("groups", "🏫 Guruhlarim (o'qituvchi)"),
            BotCommand("attendance", "🗓 Davomat olish"),
            BotCommand("attendance_report", "📊 Davomat hisoboti"),
            BotCommand("students", "👥 Guruh o'quvchilari"),
            BotCommand("essay_results", "📝 Guruh esse natijalari"),
            BotCommand("group_report", "📈 Guruh hisoboti"),
            BotCommand("arena", "⚔️ 1v1 Arena — ELO reyting"),
            BotCommand("arena_join", "Invite kod bilan xonaga qo'shilish"),
        ]
    )
    logger.info("Bot commands menu set.")



# ===========================================================================
# 2 & 3-MODUL: Ustozlar Moliya CRM (/finance) va 4-MODUL: Lug'at (/vocab)
# ===========================================================================

async def finance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Ustozlar uchun oylik moliyaviy hisobot va qarzdorlar boshqaruvi.
    /finance
    """
    if not update.effective_user or not update.message:
        return

    from apps.accounts.models import User
    from apps.courses.models import StudentGroup, GroupEnrollment
    from apps.webapi.views_crm import sync_group_students
    from asgiref.sync import sync_to_async

    user = await sync_to_async(
        lambda: User.objects.filter(telegram_chat_id=update.effective_user.id).first()
    )()

    if not user:
        await update.message.reply_text(
            "⚠️ Sizning Telegram hisobingiz platformaga ulanmagan.\n"
            "Avval saytga kirib yoki /start bosib profilingizni bog'lang."
        )
        return

    # Ustoz yoki admin bo'lishi kerak
    if user.role not in (User.Role.TEACHER, User.Role.ADMIN) and not user.is_staff:
        await update.message.reply_text(
            "ℹ️ <b>/finance</b> buyrug'i faqat ustozlar va markaz ma'murlari uchun mo'ljallangan.\n\n"
            "O'quvchi sifatida to'lovingizni tekshirish uchun: <b>/mytuition</b> buyrug'idan foydalaning.",
            parse_mode=ParseMode.HTML,
        )
        return

    def get_finance_data():
        groups = StudentGroup.objects.filter(teacher=user)
        total_students = 0
        total_collected = 0
        total_pending = 0
        debtors = []
        today = timezone.localdate()

        for g in groups:
            sync_group_students(g)
            enrollments = g.group_enrollments.filter(is_active=True).select_related("student")
            for e in enrollments:
                total_students += 1
                e.update_status(today)
                if e.payment_status == GroupEnrollment.PaymentStatus.PAID:
                    total_collected += float(e.monthly_fee)
                else:
                    total_pending += float(e.monthly_fee)
                    debtors.append({
                        "name": e.student.get_full_name(),
                        "group": g.name,
                        "due": e.next_payment_due.strftime("%d.%m.%Y") if e.next_payment_due else "Muddatsiz",
                        "fee": float(e.monthly_fee),
                        "status": "Muddati o'tgan" if e.payment_status == GroupEnrollment.PaymentStatus.OVERDUE else "To'lov yaqin",
                    })
        return {
            "groups_count": groups.count(),
            "total_students": total_students,
            "total_collected": total_collected,
            "total_pending": total_pending,
            "debtors": debtors,
        }

    data = await sync_to_async(get_finance_data)()

    groups_cnt = data["groups_count"]
    tot_st = data["total_students"]
    coll_str = f"{data['total_collected']:,.0f} so'm".replace(",", " ")
    pend_str = f"{data['total_pending']:,.0f} so'm".replace(",", " ")
    debtors_list = data["debtors"]

    lines = [
        f"📊 <b>USTOZ MOLIYAVIY XULOSASI (CRM)</b>",
        f"━━━━━━━━━━━━━━━━━━",
        f"👥 Guruhlar soni: <b>{groups_cnt} ta</b>",
        f"🎓 Umumiy o'quvchilar: <b>{tot_st} nafar</b>",
        f"🟢 Yig'ilgan tushum: <b>{coll_str}</b>",
        f"🔴 Kutilayotgan qarzdorlik: <b>{pend_str}</b>",
        f"━━━━━━━━━━━━━━━━━━",
    ]

    if debtors_list:
        lines.append(f"⚠️ <b>Qarzdor o'quvchilar ({len(debtors_list)} nafar):</b>")
        for idx, d in enumerate(debtors_list[:10], 1):
            fee_d = f"{d['fee']:,.0f} so'm".replace(",", " ")
            lines.append(f"{idx}. <b>{d['name']}</b> ({d['group']}) — {fee_d} [{d['status']}]")
        if len(debtors_list) > 10:
            lines.append(f"<i>...va yana {len(debtors_list) - 10} nafar o'quvchi</i>")
    else:
        lines.append("🎉 Barcha o'quvchilar to'lovlarni o'z vaqtida amalga oshirgan!")

    keyboard = []
    if debtors_list:
        keyboard.append([
            InlineKeyboardButton(
                "📢 Barcha qarzdorlarga eslatma yuborish",
                callback_data="crm_remind_all_debtors",
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
    )


async def vocab_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    O'quvchilar uchun Ebbinghaus interval takrorlash viktorinasi (/vocab).
    Bugungi adashgan 5 ta eng qiyin so'z.
    """
    if not update.effective_user or not update.message:
        return

    from apps.accounts.models import User
    from apps.vocabulary.models import StudentWordMistake
    from asgiref.sync import sync_to_async
    import random

    user = await sync_to_async(
        lambda: User.objects.filter(telegram_chat_id=update.effective_user.id).first()
    )()

    if not user:
        await update.message.reply_text(
            "⚠️ So'zlar viktorinasini boshlash uchun Telegram hisobingizni saytga bog'lang (/start)."
        )
        return

    def get_vocab_word():
        mistakes = list(
            StudentWordMistake.objects.filter(student=user, is_mastered=False)
            .order_by("-mistake_count", "next_review_at")[:10]
        )
        if mistakes:
            chosen = random.choice(mistakes)
            word = chosen.word
            meaning = chosen.translation_uz or chosen.definition or "To'g'ri tarjima"
            streak = chosen.consecutive_correct_streak
            mistake_id = chosen.id
        else:
            samples = [
                ("resilient", "bardoshli, chidamli"),
                ("persistent", "qat'iyatli, sobitqadam"),
                ("meticulous", "o'ta ehtiyotkor"),
                ("ubiquitous", "hamma joyda uchraydigan"),
                ("lucid", "aniq, tushunarli"),
            ]
            chosen_s = random.choice(samples)
            word = chosen_s[0]
            meaning = chosen_s[1]
            streak = 0
            mistake_id = 0

        distractors = ["tezkor qaror", "qoniqarsiz natija", "noma'lum xulosa", "qarama-qarshi holat"]
        opts = [meaning] + random.sample(distractors, 3)
        random.shuffle(opts)
        return {
            "id": mistake_id,
            "word": word,
            "correct": meaning,
            "options": opts,
            "streak": streak,
        }

    vocab_data = await sync_to_async(get_vocab_word)()

    # Send as Telegram Poll (Quiz)
    correct_idx = vocab_data["options"].index(vocab_data["correct"])
    poll_question = f"🧠 '{vocab_data['word']}' so'zining to'g'ri tarjimasi qaysi? (Streak: {vocab_data['streak']}/3)"

    await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=poll_question,
        options=vocab_data["options"],
        type="quiz",
        correct_option_id=correct_idx,
        is_anonymous=False,
        explanation=f"'{vocab_data['word']}' = {vocab_data['correct']}. Ketma-ket 3 marta to'g'ri topsangiz, to'liq yod olinadi!",
    )
