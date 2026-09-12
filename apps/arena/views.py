"""
Arena views — lobby, duel room, live leaderboard, JSON API.

Endpoints:
    GET  /arena/                       — Lobby (queue, custom rooms, leaderboard)
    GET  /arena/<room_code>/           — Duel room page
    GET  /arena/api/leaderboard/       — Top players by ELO rating (JSON)
    GET  /arena/api/stats/             — My arena stats (JSON)
    GET  /arena/api/invites/           — My pending custom-room invites (JSON)
    POST /arena/api/rooms/create/      — Create a custom room with invite code
    POST /arena/api/rooms/join/        — Join a custom room by invite code
    POST /arena/api/queue/             — Join the matchmaking queue (REST shortcut)
"""
from django.contrib.auth.decorators import login_required
from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import services
from .models import ArenaPlayer, ArenaProfile, ArenaRoom


def _leaderboard_rows(limit: int = 50):
    """Top players by ELO rating, excluding bot accounts (ranked)."""
    rows = (
        ArenaProfile.objects.filter(user__is_bot=False)
        .select_related("user")
        .annotate(
            rank=Window(
                expression=RowNumber(),
                order_by=F("rating").desc(),
            )
        )
        .order_by("-rating")[:limit]
    )
    return [
        {
            "rank": r.rank,
            "user_id": r.user_id,
            "name": r.user.get_full_name() or r.user.email,
            "rating": r.rating,
            "wins": r.wins,
            "losses": r.losses,
            "draws": r.draws,
            "win_streak": r.current_win_streak,
            "duels": r.duels_played,
            "accuracy": r.accuracy,
        }
        for r in rows
    ]


def _my_stats(user) -> dict:
    profile = services.get_or_create_profile(user)
    rank = ArenaProfile.objects.filter(
        user__is_bot=False, rating__gt=profile.rating
    ).count() + 1

    # XP/coins earned through duels (games economy)
    xp = coins = 0
    try:
        score = user.game_scores.filter(game__slug=services.ARENA_GAME_SLUG).first()
        if score:
            xp, coins = score.total_xp, score.total_coins
    except Exception:
        pass

    return {
        "rating": profile.rating,
        "rank": rank,
        "wins": profile.wins,
        "losses": profile.losses,
        "draws": profile.draws,
        "duels_played": profile.duels_played,
        "current_win_streak": profile.current_win_streak,
        "best_win_streak": profile.best_win_streak,
        "total_correct": profile.total_correct,
        "total_answers": profile.total_answers,
        "accuracy": profile.accuracy,
        "win_rate": profile.win_rate,
        "total_time_seconds": profile.total_time_seconds,
        "xp": xp,
        "coins": coins,
    }


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@login_required
def arena_lobby_view(request: HttpRequest) -> HttpResponse:
    """Arena lobby — queue, custom rooms, live leaderboard, my stats."""
    active_rooms = (
        ArenaRoom.objects.filter(status__in=[ArenaRoom.Status.WAITING, ArenaRoom.Status.STARTED])
        .select_related("player1", "player2", "bot_user")
        [:10]
    )

    user_matches = (
        ArenaPlayer.objects.filter(player=request.user)
        .select_related("room", "room__player1", "room__player2", "room__winner")
        .order_by("-room__created_at")[:5]
    )

    # My pending custom-room invites
    my_invites = (
        ArenaRoom.objects.filter(
            player1=request.user,
            mode=ArenaRoom.Mode.CUSTOM,
            status=ArenaRoom.Status.WAITING,
        )
        .order_by("-created_at")
    )

    protocol = "wss" if request.is_secure() else "ws"
    return render(request, "arena/lobby.html", {
        "active_rooms": active_rooms,
        "user_matches": user_matches,
        "my_invites": my_invites,
        "my_stats": _my_stats(request.user),
        "leaderboard": _leaderboard_rows(10),
        "queue_count": ArenaRoom.objects.filter(
            status=ArenaRoom.Status.WAITING, mode=ArenaRoom.Mode.QUEUE
        ).count(),
        "bot_fallback_seconds": int(services._bot_fallback_seconds()),
        "ws_url": f"{protocol}://{request.get_host()}/ws/arena/",
    })


@login_required
def arena_room_view(request: HttpRequest, room_code: str) -> HttpResponse:
    """Duel room — real-time WebSocket game."""
    room = get_object_or_404(
        ArenaRoom.objects.select_related("player1", "player2", "bot_user"),
        room_code=room_code,
    )

    # Only participants may enter
    if request.user.id not in (room.player1_id, room.player2_id):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Bu xonaning ishtirokchisi emassiz.")

    protocol = "wss" if request.is_secure() else "ws"
    return render(request, "arena/duel_room.html", {
        "room": room,
        "room_code": room_code,
        "is_bot_duel": room.mode == ArenaRoom.Mode.BOT,
        "my_stats": _my_stats(request.user),
        "ws_url": f"{protocol}://{request.get_host()}/ws/arena/{room_code}/",
    })


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------

@login_required
def arena_api_leaderboard(request: HttpRequest) -> JsonResponse:
    """GET /arena/api/leaderboard/ — top 50 by ELO."""
    return JsonResponse({"leaderboard": _leaderboard_rows(50)})


@login_required
def arena_api_stats(request: HttpRequest) -> JsonResponse:
    """GET /arena/api/stats/ — my arena stats."""
    return JsonResponse({"stats": _my_stats(request.user)})


@login_required
def arena_api_invites(request: HttpRequest) -> JsonResponse:
    """GET /arena/api/invites/ — my pending custom-room invite codes."""
    rooms = (
        ArenaRoom.objects.filter(
            player1=request.user,
            mode=ArenaRoom.Mode.CUSTOM,
            status=ArenaRoom.Status.WAITING,
        )
        .order_by("-created_at")
    )
    return JsonResponse({
        "invites": [
            {
                "room_code": r.room_code,
                "created_at": r.created_at.isoformat(),
                "total_questions": r.total_questions,
            }
            for r in rooms
        ],
    })


@csrf_exempt
@login_required
@require_POST
def arena_api_room_create(request: HttpRequest) -> JsonResponse:
    """POST /arena/api/rooms/create/ — create a custom room with invite code."""
    room = services.create_custom_room(request.user)
    return JsonResponse({
        "room_code": room.room_code,
        "url": f"/arena/{room.room_code}/",
        "message": "Xona yaratildi. Invite kodni do'stingizga yuboring.",
    }, status=201)


@csrf_exempt
@login_required
@require_POST
def arena_api_room_join(request: HttpRequest) -> JsonResponse:
    """POST /arena/api/rooms/join/ — join a custom room by invite code."""
    code = request.POST.get("code", "")
    if not code and request.body:
        try:
            import json as _json
            body = _json.loads(request.body)
            code = body.get("code", "") if isinstance(body, dict) else ""
        except Exception:
            code = ""
    code = str(code or "").strip().upper()

    room, error = services.join_custom_room(code, request.user)
    if room is None:
        return JsonResponse({"error": error or "Xonaga qo'shib bo'lmadi."}, status=400)

    return JsonResponse({
        "room_code": room.room_code,
        "url": f"/arena/{room.room_code}/",
        "message": "Xonaga qo'shildingiz! Duel boshlanmoqda.",
    })


@csrf_exempt
@login_required
@require_POST
def arena_api_queue(request: HttpRequest) -> JsonResponse:
    """POST /arena/api/queue/ — join matchmaking queue (REST convenience)."""
    entry, room = services.join_matchmaking_queue(request.user)
    if room is not None:
        return JsonResponse({
            "matched": True,
            "room_code": room.room_code,
            "url": f"/arena/{room.room_code}/",
        })
    return JsonResponse({
        "matched": False,
        "position": services.queue_position(request.user),
        "bot_fallback_seconds": int(services._bot_fallback_seconds()),
    })