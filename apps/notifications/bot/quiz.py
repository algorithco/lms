"""
Telegram Quiz Handler — Bot orqali test topshirish.

Flow:
    /quiz → Testlar ro'yxati → Test tanlash → Savollar → Javoblar → Natija

Features:
    - Inline keyboard orqali javob berish
    - Har bir savol uchun vaqt cheklovi (umumiy)
    - To'g'ri/noto'g'ri javob ko'rsatish
    - Yakuniy natija + ball
"""
from __future__ import annotations

import logging
import random
from typing import Any, TYPE_CHECKING

from asgiref.sync import sync_to_async
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = logging.getLogger(__name__)

# Quiz state keys in context.user_data
QUIZ_KEY = "quiz"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run_db(func, *args, **kwargs):
    """Run sync Django DB operation from async context."""
    return await sync_to_async(func)(*args, **kwargs)


def _get_or_create_user_sync(update: Update) -> "User | None":
    """Get or create a user using only Telegram's immutable numeric ID."""
    from apps.accounts.services.telegram_identity import get_or_create_telegram_user
    from apps.accounts.services.telegram_identity import TelegramIdentityUnverified

    tg_user = update.effective_user
    if not tg_user:
        return None
    try:
        user, _created = get_or_create_telegram_user({
            "id": tg_user.id,
            "first_name": tg_user.first_name or "",
            "last_name": tg_user.last_name or "",
        })
    except TelegramIdentityUnverified:
        logger.warning("Legacy Telegram identity requires verification: tg_id=%d", tg_user.id)
        return None
    return user if user.is_active else None


_get_or_create_user_async = sync_to_async(_get_or_create_user_sync)


async def _save_quiz_result(
    user: "User",
    quiz: dict,
    correct: int,
    total: int,
    percentage: float,
) -> None:
    """Async wrapper around _save_quiz_result_sync (kept for compatibility)."""
    await _run_db(_save_quiz_result_sync, user, quiz)


# ---------------------------------------------------------------------------
# /quiz — Start quiz flow
# ---------------------------------------------------------------------------

async def quiz_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /quiz command — show available tests for quiz."""
    user = await _get_or_create_user_async(update)
    if not user:
        await update.message.reply_text("Xatolik yuz berdi. Qayta urinib ko'ring.")
        return

    from apps.tests.models import Test

    tests = await _run_db(
        lambda: list(
            Test.objects.filter(is_active=True)
            .select_related("course")
            .order_by("-created_at")[:10]
        )
    )

    if not tests:
        await update.message.reply_text(
            "📝 Hozircha mavjud testlar yo'q.\n\n"
            "O'qituvchilar yangi testlar yaratganda, ular shu yerda paydo bo'ladi."
        )
        return

    text = "🧠 *TELEGRAM QUIZ*\n\n"
    text += "Testni tanlang va Telegram'da javob bering!\n\n"

    buttons = []
    for test in tests:
        diff = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(test.difficulty, "⚪")
        buttons.append([
            InlineKeyboardButton(
                f"{diff} {test.title[:35]} ({test.total_questions} savol)",
                callback_data=f"quiz_start_{test.id}",
            )
        ])

    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")])

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------------------------------------------------------------------------
# Quiz flow callbacks
# ---------------------------------------------------------------------------

async def quiz_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handle quiz-related callback queries.
    Returns True if handled, False otherwise.
    """
    query = update.callback_query
    data = query.data

    if not data.startswith("quiz_"):
        return False

    await query.answer()

    if data.startswith("quiz_start_"):
        test_id = int(data.split("_")[-1])
        await _start_quiz(update, context, test_id)
    elif data == "quiz_confirm":
        await _confirm_start(update, context)
    elif data.startswith("quiz_answer_"):
        parts = data.split("_")
        question_idx = int(parts[2])
        choice_idx = int(parts[3])
        await _handle_answer(update, context, question_idx, choice_idx)
    elif data == "quiz_next":
        await _show_next_question(update, context)
    elif data == "quiz_finish":
        await _show_final_results(update, context)

    return True


async def _start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, test_id: int) -> None:
    """Load test questions and show confirmation."""
    query = update.callback_query

    def _load_test():
        from apps.tests.models import Test
        test = Test.objects.filter(id=test_id, is_active=True).first()
        if not test:
            return None

        questions = list(
            # Text-match questions have no choices to render as inline buttons
            test.questions.exclude(question_type="text")
            .prefetch_related("choices")
            .order_by("position")
        )
        return test, questions

    result = await _run_db(_load_test)

    if not result:
        await query.edit_message_text("❌ Test topilmadi yoki faol emas.")
        return

    test, questions = result

    if not questions:
        await query.edit_message_text("❌ Bu testda savollar yo'q.")
        return

    # Shuffle questions
    random.shuffle(questions)

    # Store quiz state in context.user_data
    quiz_data = {
        "test_id": test.id,
        "test_title": test.title,
        "questions": [],
        "current_idx": 0,
        "answers": {},  # {question_idx: choice_idx}
        "correct_count": 0,
        "total_questions": len(questions),
    }

    for q in questions:
        choices = list(q.choices.all())
        random.shuffle(choices)
        quiz_data["questions"].append({
            "id": q.id,
            "text": q.text,
            "points": q.points,
            "choices": [
                {"id": c.id, "text": c.text, "is_correct": c.is_correct}
                for c in choices
            ],
        })

    context.user_data[QUIZ_KEY] = quiz_data

    # Show confirmation
    text = (
        f"🧠 *{test.title}*\n\n"
        f"📚 Kurs: {test.course.title}\n"
        f"❓ Savollar: *{len(questions)}*\n"
        f"⏱ Vaqt: *{test.time_limit_minutes} daqiqa*\n"
        f"🎯 O'tish: *{test.pass_percentage}%*\n\n"
        f"Testni boshlashga tayyormisiz?"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Boshlash", callback_data="quiz_confirm")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="menu_main")],
    ])

    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=buttons)


async def _confirm_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the quiz — show first question."""
    quiz = context.user_data.get(QUIZ_KEY)
    if not quiz:
        await update.callback_query.edit_message_text("❌ Quiz topilmadi. /quiz bilan qayta boshlang.")
        return

    await _show_question(update, context, quiz["current_idx"])


async def _show_question(update: Update, context: ContextTypes.DEFAULT_TYPE, idx: int) -> None:
    """Show a single question with inline keyboard choices."""
    query = update.callback_query
    quiz = context.user_data.get(QUIZ_KEY)

    if not quiz or idx >= quiz["total_questions"]:
        await _show_final_results(update, context)
        return

    q = quiz["questions"][idx]
    total = quiz["total_questions"]

    text = (
        f"📝 *Savol {idx + 1}/{total}*\n\n"
        f"{q['text']}\n"
    )

    # Build choices keyboard
    buttons = []
    labels = ["A", "B", "C", "D"]
    for i, choice in enumerate(q["choices"]):
        buttons.append([
            InlineKeyboardButton(
                f"{labels[i]}. {choice['text'][:50]}",
                callback_data=f"quiz_answer_{idx}_{i}",
            )
        ])

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def _handle_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    question_idx: int,
    choice_idx: int,
) -> None:
    """Process user's answer, show feedback, then move to next question."""
    query = update.callback_query
    quiz = context.user_data.get(QUIZ_KEY)

    if not quiz:
        await query.edit_message_text("❌ Quiz topilmadi.")
        return

    if question_idx >= quiz["total_questions"]:
        await _show_final_results(update, context)
        return

    q = quiz["questions"][question_idx]
    selected = q["choices"][choice_idx]

    # All-or-none grading, same rule as SubmitAttemptService: single-select
    # questions are correct only when the chosen option is the (only) correct
    # one; multi-select questions can't be satisfied by a single tap, so the
    # shown feedback always matches the final server-side result.
    correct_choice_total = sum(1 for c in q["choices"] if c["is_correct"])
    is_correct = bool(selected["is_correct"]) and correct_choice_total == 1

    # Save answer
    quiz["answers"][question_idx] = choice_idx
    if is_correct:
        quiz["correct_count"] += 1

    # Show feedback
    labels = ["A", "B", "C", "D"]
    correct_label = ""
    for i, c in enumerate(q["choices"]):
        if c["is_correct"]:
            correct_label = f"{labels[i]}. {c['text'][:50]}"
            break

    if is_correct:
        emoji = "✅"
        result_text = "To'g'ri javob! 🎉"
    else:
        emoji = "❌"
        result_text = f"To'g'ri javob: *{correct_label}*"

    text = (
        f"{emoji} *Savol {question_idx + 1}/{quiz['total_questions']}*\n\n"
        f"{q['text']}\n\n"
        f"Javobingiz: *{labels[choice_idx]}. {selected['text'][:50]}*\n"
        f"{result_text}\n\n"
        f"📊 Hozirgi hisob: *{quiz['correct_count']}/{quiz['total_questions']}*"
    )

    # Next question or finish
    next_idx = question_idx + 1
    if next_idx < quiz["total_questions"]:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("➡️ Keyingi savol", callback_data="quiz_next")],
        ])
    else:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Natijani ko'rish", callback_data="quiz_finish")],
        ])

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=buttons,
    )


async def _show_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the next question."""
    quiz = context.user_data.get(QUIZ_KEY)
    if not quiz:
        await update.callback_query.edit_message_text("❌ Quiz topilmadi.")
        return

    next_idx = quiz["current_idx"] + 1
    quiz["current_idx"] = next_idx

    await _show_question(update, context, next_idx)


async def _show_final_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show quiz final results with score and save to database."""
    query = update.callback_query
    quiz = context.user_data.get(QUIZ_KEY)

    if not quiz:
        await query.edit_message_text("❌ Quiz topilmadi.")
        return

    # --- Save result via the official test-attempt flow (best-effort) ------
    user = await _get_or_create_user_async(update)
    saved = None
    if user:
        try:
            saved = await _run_db(_save_quiz_result_sync, user, quiz)
        except Exception:
            # Saving must NEVER break showing the result to the user
            logger.exception("Quiz result save failed (non-fatal): user=%s", getattr(user, "email", "?"))

    # --- Prefer official (server-graded) numbers when available ------------
    if saved:
        total = saved["total"]
        correct = saved["correct"]
        percentage = saved["percentage"]
        passed = saved["is_passed"]
    else:
        total = quiz["total_questions"]
        correct = quiz["correct_count"]
        percentage = round(correct / total * 100, 1) if total > 0 else 0
        passed = percentage >= 60

    # Grade emoji
    if percentage >= 90:
        grade = "A+ 🌟"
    elif percentage >= 80:
        grade = "A ✨"
    elif percentage >= 70:
        grade = "B 💪"
    elif percentage >= 60:
        grade = "C 👍"
    elif percentage >= 50:
        grade = "D 😐"
    else:
        grade = "F 😔"

    status = "✅ O'tdi!" if passed else "❌ O'tmadi"

    text = (
        f"📊 *QUIZ NATIJASI*\n\n"
        f"📝 Test: *{quiz['test_title']}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ To'g'ri: *{correct}/{total}*\n"
        f"📈 Foiz: *{percentage}%*\n"
        f"🎓 Baho: *{grade}*\n"
        f"📋 Holat: {status}\n"
    )

    if passed:
        text += (
            f"\n🎉 *Tabriklaymiz!*\n"
            f"Siz muvaffaqiyatli testdan o'tdingiz!\n"
        )
    else:
        text += (
            f"\n💡 *Tavsiya:*\n"
            f"Ko'proq mashq qiling va qayta urinib ko'ring!\n"
        )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Qayta urinish", callback_data=f"quiz_start_{quiz['test_id']}")],
        [InlineKeyboardButton("📝 Boshqa testlar", callback_data="menu_tests")],
        [InlineKeyboardButton("📊 Natijalarim", callback_data="menu_results")],
        [InlineKeyboardButton("🔙 Bosh menyu", callback_data="menu_main")],
    ])

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=buttons,
    )

    # Clean up quiz state
    context.user_data.pop(QUIZ_KEY, None)


# Slug of the Game row used to track XP earned through the Telegram quiz.
_QUIZ_GAME_SLUG = "telegram_quiz"


def _save_quiz_result_sync(user: "User", quiz: dict) -> dict | None:
    """
    Save the Telegram quiz through the OFFICIAL test-attempt pipeline.

    The old implementation tried to create Result rows without an attempt or
    course and used UserGameScore.get_or_create(game_name=...) — neither field
    exists, so every finished Telegram quiz crashed before the result screen.

    This implementation:
        1. Starts a real TestAttempt via StartAttemptService
        2. Records every answer via SaveAnswerService
        3. Grades via SubmitAttemptService (produces Result + notifications)
        4. Awards quiz XP/coins through a real Game row

    Returns a dict {"correct", "total", "percentage", "is_passed"} on success
    or None if nothing could be saved (never raises).
    """
    from django.db import IntegrityError
    from django.db.models import F
    from django.utils import timezone

    from apps.tests.models import Test
    from apps.tests.services import (
        SaveAnswerService,
        StartAttemptService,
        SubmitAttemptService,
    )

    test = Test.objects.filter(id=quiz["test_id"], is_active=True).first()
    if not test:
        logger.warning("Quiz save: test %s not found/inactive", quiz.get("test_id"))
        return None

    # 1) Start an official attempt
    try:
        attempt = StartAttemptService.execute(test_id=test.id, student=user)
    except ValueError as exc:
        # e.g. max_attempts reached, active attempt already in progress, or
        # the user is not a student — nothing we can (or should) record.
        logger.warning("Quiz save: could not start attempt: %s", exc)
        return None

    # 2) Record answers + 3) grade through the official pipeline
    try:
        questions = quiz["questions"]
        for idx, choice_idx in quiz.get("answers", {}).items():
            q = questions[idx]
            selected = q["choices"][choice_idx]
            SaveAnswerService.execute(
                attempt_id=attempt.id,
                question_id=q["id"],
                choice_ids=[selected["id"]],
                student=user,
            )

        attempt_result = SubmitAttemptService.execute(attempt_id=attempt.id, student=user)
        result_numbers = {
            "correct": attempt_result.correct_answers,
            "total": attempt_result.total_questions,
            "percentage": float(attempt_result.percentage),
            "is_passed": attempt_result.is_passed,
        }
    except Exception as exc:
        # Double-submit / timeout races can raise — recover from the Result
        # if one exists, otherwise give up quietly.
        logger.warning("Quiz grading failed for attempt=%d: %s", attempt.id, exc)
        try:
            from apps.results.models import Result
            result = Result.objects.get(attempt=attempt)
        except Exception:
            return None
        result_numbers = {
            "correct": result.correct_answers,
            "total": result.total_questions,
            "percentage": float(result.percentage),
            "is_passed": result.is_passed,
        }

    # 4) Award quiz XP/coins via a real Game row
    try:
        from apps.games.models import Game, UserGameScore

        game = Game.objects.filter(slug=_QUIZ_GAME_SLUG).first()
        if game is None:
            try:
                game = Game.objects.create(
                    name="Telegram Quiz",
                    slug=_QUIZ_GAME_SLUG,
                    description="Telegram bot orqali test topshirish.",
                    icon_emoji="🧠",
                    # Hidden from the web game listings — it exists purely to
                    # track XP/coins earned through Telegram quizzes.
                    is_active=False,
                )
            except IntegrityError:  # concurrent creation
                game = Game.objects.get(slug=_QUIZ_GAME_SLUG)

        score_row, _ = UserGameScore.objects.get_or_create(user=user, game=game)
        UserGameScore.objects.filter(pk=score_row.pk).update(
            total_xp=F("total_xp") + result_numbers["correct"] * 10,
            total_coins=F("total_coins") + result_numbers["correct"] * 5,
            games_played=F("games_played") + 1,
            last_played_at=timezone.now(),
        )
    except Exception:
        logger.exception("Quiz XP reward failed (non-fatal): user=%s", getattr(user, "email", "?"))

    return result_numbers
