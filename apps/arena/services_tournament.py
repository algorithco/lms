"""
Services for Sunday Live League & Real-time E-Sport Tournaments.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from apps.arena.models import Tournament, TournamentParticipant

logger = logging.getLogger(__name__)


def get_tournament_leaderboard(tournament_id: int) -> list[dict[str, Any]]:
    """Return sorted leaderboard for a tournament."""
    participants = (
        TournamentParticipant.objects.filter(tournament_id=tournament_id)
        .select_related("user")
        .order_by("rank", "-score", "time_taken_seconds")[:50]
    )
    result = []
    for idx, p in enumerate(participants, 1):
        effective_rank = p.rank or idx
        full_name = p.user.get_full_name() or p.user.email
        result.append(
            {
                "rank": effective_rank,
                "user_id": p.user_id,
                "name": full_name,
                "score": float(p.score),
                "correct_answers": p.correct_answers,
                "total_questions": p.total_questions,
                "time_taken_seconds": p.time_taken_seconds,
                "is_finished": p.is_finished,
            }
        )
    return result


@transaction.atomic
def submit_tournament_answers(
    tournament_id: int,
    user: Any,
    answers_dict: dict[str, str],
    time_taken_seconds: int,
) -> dict[str, Any]:
    """
    Submit test answers for tournament and update real-time rankings.
    """
    tournament = Tournament.objects.select_related("test").get(id=tournament_id)
    participant, _ = TournamentParticipant.objects.get_or_create(
        tournament=tournament,
        user=user,
    )

    test = tournament.test
    questions = list(
        test.questions.all().prefetch_related("choices").order_by("position")
    )
    total_q = len(questions) or 1
    correct_count = 0
    letters = ["A", "B", "C", "D", "E", "F"]

    for q in questions:
        submitted_key = answers_dict.get(str(q.id)) or answers_dict.get(q.id)
        if not submitted_key:
            continue
        submitted_str = str(submitted_key).strip()

        is_correct = False
        choices = list(q.choices.all().order_by("position"))
        if choices:
            for idx, ch in enumerate(choices):
                letter = letters[idx] if idx < len(letters) else str(idx + 1)
                if ch.is_correct:
                    if (
                        submitted_str.upper() == letter
                        or submitted_str == str(ch.id)
                        or submitted_str.lower() == ch.text.lower()
                    ):
                        is_correct = True
                        break
        elif hasattr(q, "correct_answer") and q.correct_answer:
            if submitted_str.upper() == str(q.correct_answer).strip().upper():
                is_correct = True
        elif hasattr(q, "correct_text") and q.correct_text:
            if submitted_str.lower() == str(q.correct_text).strip().lower():
                is_correct = True

        if is_correct:
            correct_count += 1

    score = Decimal(str(round((correct_count / total_q) * 100, 2)))

    participant.score = score
    participant.correct_answers = correct_count
    participant.total_questions = total_q
    participant.time_taken_seconds = max(1, int(time_taken_seconds))
    participant.is_finished = True
    participant.finished_at = timezone.now()
    participant.save()

    # Recalculate ranks for all finished participants in this tournament
    all_participants = list(
        TournamentParticipant.objects.filter(
            tournament_id=tournament_id,
            is_finished=True,
        ).order_by("-score", "time_taken_seconds")
    )
    for index, part in enumerate(all_participants, start=1):
        part.rank = index
    TournamentParticipant.objects.bulk_update(all_participants, ["rank"])

    # Broadcast to channels group if channels layer is active
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"tournament_{tournament_id}",
                {
                    "type": "tournament_leaderboard_update",
                    "leaderboard": get_tournament_leaderboard(tournament_id),
                },
            )
    except Exception as e:
        logger.warning("Could not broadcast tournament update: %s", e)

    participant.refresh_from_db()
    return {
        "score": float(participant.score),
        "correct_answers": participant.correct_answers,
        "total_questions": participant.total_questions,
        "rank": participant.rank,
        "time_taken_seconds": participant.time_taken_seconds,
    }


def finalize_tournament_awards(tournament_id: int) -> dict[str, Any]:
    """
    Finalize a finished tournament and grant prizes to top 3 ranks:
    - 1st place: 1 month Premium
    - 2nd & 3rd place: 1 month Starter
    """
    tournament = Tournament.objects.get(id=tournament_id)
    tournament.status = Tournament.Status.FINISHED
    tournament.save(update_fields=["status", "updated_at"])

    top_participants = (
        TournamentParticipant.objects.filter(
            tournament_id=tournament_id, is_finished=True
        )
        .select_related("user")
        .order_by("rank", "-score", "time_taken_seconds")[:3]
    )

    from apps.payments.models import SubscriptionPlan, UserSubscription
    from apps.notifications.services.telegram_service import TelegramService

    premium_plan = (
        SubscriptionPlan.objects.filter(plan_type="premium").first()
        or SubscriptionPlan.objects.filter(plan_type="pro").first()
    )
    starter_plan = (
        SubscriptionPlan.objects.filter(plan_type="starter").first()
        or SubscriptionPlan.objects.filter(plan_type="start").first()
    )
    now = timezone.now()
    awarded = []

    for p in top_participants:
        u = p.user
        plan_to_give = premium_plan if p.rank == 1 else starter_plan
        if plan_to_give:
            sub, _ = UserSubscription.objects.get_or_create(
                user=u,
                defaults={
                    "plan": plan_to_give,
                    "status": UserSubscription.Status.ACTIVE,
                },
            )
            sub.plan = plan_to_give
            sub.status = UserSubscription.Status.ACTIVE
            sub.started_at = now
            sub.expires_at = now + timedelta(days=30)
            sub.save()

        # Update profile plan string as well
        if hasattr(u, "profile"):
            u.profile.plan = "premium" if p.rank == 1 else "starter"
            u.profile.save(update_fields=["plan"])

        # Send congratulation telegram message
        if u.telegram_chat_id:
            badge_icon = (
                "🥇 OLTIN KUBOK"
                if p.rank == 1
                else ("🥈 KUMUSH MEDAL" if p.rank == 2 else "🥉 BRONZA MEDAL")
            )
            prize_name = (
                "1 oylik bepul Premium obuna"
                if p.rank == 1
                else "1 oylik bepul Starter obuna"
            )
            msg = (
                f"🏆 <b>TABRIKLAYMIZ! SIZ TURNIR G'OLIBISIZ!</b>\n\n"
                f"📌 <b>Turnir:</b> {tournament.title}\n"
                f"🏅 <b>O'rningiz:</b> {p.rank}-o'rin ({badge_icon})\n"
                f"📊 <b>To'plagan ballingiz:</b> {p.score} ball ({p.time_taken_seconds} sek)\n"
                f"🎁 <b>Mukofotingiz:</b> {prize_name} hisobingizga avtomatik biriktirildi!\n\n"
                f"<i>GRAND EDUCATION e-Sport ligasida qatnashganingiz uchun tashakkur!</i>"
            )
            try:
                TelegramService.send_message(
                    chat_id=u.telegram_chat_id,
                    text=msg,
                    recipient=u,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning("Failed sending winner notification: %s", e)

        awarded.append(
            {
                "user_id": u.id,
                "name": u.get_full_name(),
                "rank": p.rank,
                "score": float(p.score),
            }
        )

    return {"status": "finished", "awarded": awarded}
