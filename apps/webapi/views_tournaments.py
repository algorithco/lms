"""
Web API endpoints for Sunday Live League & Tournaments.
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.arena.models import Tournament, TournamentParticipant
from apps.arena.services_tournament import (
    finalize_tournament_awards,
    get_tournament_leaderboard,
    submit_tournament_answers,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def tournament_list_view(request):
    """
    List all tournaments with their status and basic info.
    """
    tournaments = Tournament.objects.all().order_by("-scheduled_at")[:20]
    user = request.user if request.user.is_authenticated else None

    data = []
    for t in tournaments:
        user_joined = False
        user_score = None
        user_rank = None
        if user:
            part = TournamentParticipant.objects.filter(tournament=t, user=user).first()
            if part:
                user_joined = True
                user_score = float(part.score)
                user_rank = part.rank

        data.append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "scheduled_at": t.scheduled_at,
            "duration_minutes": t.duration_minutes,
            "status": t.status,
            "prize_fund_description": t.prize_fund_description,
            "participants_count": t.participants_count,
            "user_joined": user_joined,
            "user_score": user_score,
            "user_rank": user_rank,
        })

    return Response({"tournaments": data})


@api_view(["GET"])
@permission_classes([AllowAny])
def tournament_detail_view(request, pk):
    """
    Get detailed tournament information, including questions if live.
    """
    tournament = get_object_or_404(
        Tournament.objects.select_related("test"),
        id=pk,
    )
    user = request.user if request.user.is_authenticated else None

    my_part_data = None
    if user:
        part = TournamentParticipant.objects.filter(tournament=tournament, user=user).first()
        if part:
            my_part_data = {
                "joined": True,
                "score": float(part.score),
                "rank": part.rank,
                "is_finished": part.is_finished,
                "time_taken_seconds": part.time_taken_seconds,
            }

    # Include test questions without correct answer
    questions_data = []
    if tournament.test:
        letters = ["A", "B", "C", "D", "E", "F"]
        for q in tournament.test.questions.all().prefetch_related("choices").order_by("position"):
            options_dict = {}
            choices = list(q.choices.all().order_by("position"))
            if choices:
                for idx, ch in enumerate(choices):
                    letter = letters[idx] if idx < len(letters) else str(idx + 1)
                    options_dict[letter] = ch.text
            else:
                options_dict = {
                    "A": getattr(q, "option_a", ""),
                    "B": getattr(q, "option_b", ""),
                    "C": getattr(q, "option_c", ""),
                    "D": getattr(q, "option_d", ""),
                }
            questions_data.append({
                "id": q.id,
                "text": q.text,
                "options": options_dict,
                "order": getattr(q, "position", 1),
            })

    return Response({
        "tournament": {
            "id": tournament.id,
            "title": tournament.title,
            "description": tournament.description,
            "scheduled_at": tournament.scheduled_at,
            "duration_minutes": tournament.duration_minutes,
            "status": tournament.status,
            "prize_fund_description": tournament.prize_fund_description,
            "participants_count": tournament.participants_count,
            "questions_count": len(questions_data),
        },
        "questions": questions_data,
        "my_participation": my_part_data,
        "leaderboard": get_tournament_leaderboard(tournament.id),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def tournament_join_view(request, pk):
    """
    Join an upcoming or live tournament.
    """
    tournament = get_object_or_404(Tournament, id=pk)
    if tournament.status == Tournament.Status.FINISHED:
        return Response({"error": "Ushbu turnir allaqachon yakunlangan."}, status=status.HTTP_400_BAD_REQUEST)

    participant, created = TournamentParticipant.objects.get_or_create(
        tournament=tournament,
        user=request.user,
    )
    return Response({
        "success": True,
        "joined": True,
        "is_finished": participant.is_finished,
        "message": f"Siz '{tournament.title}' turniriga muvaffaqiyatli ro'yxatdan o'tdingiz!",
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def tournament_submit_view(request, pk):
    """
    Submit test answers for the tournament.
    """
    tournament = get_object_or_404(Tournament, id=pk)
    answers = request.data.get("answers", {})
    time_taken = request.data.get("time_taken_seconds", 0)

    result = submit_tournament_answers(
        tournament_id=tournament.id,
        user=request.user,
        answers_dict=answers,
        time_taken_seconds=time_taken,
    )

    return Response({
        "success": True,
        "result": result,
        "leaderboard": get_tournament_leaderboard(tournament.id),
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def tournament_leaderboard_view(request, pk):
    """
    Public leaderboard for a tournament.
    """
    tournament = get_object_or_404(Tournament, id=pk)
    return Response({
        "tournament_id": tournament.id,
        "title": tournament.title,
        "status": tournament.status,
        "leaderboard": get_tournament_leaderboard(tournament.id),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def tournament_finalize_view(request, pk):
    """
    Admin: Finalize tournament and grant awards.
    """
    if not (request.user.role == "admin" or request.user.is_staff):
        return Response({"error": "Faqat admin turnirni yakunlashi mumkin."}, status=status.HTTP_403_FORBIDDEN)

    res = finalize_tournament_awards(pk)
    return Response(res)
