"""
Telegram Mini App views — auto-login, auto-register, TMA page.

Flow:
    1. User opens TMA in Telegram → Telegram sends initData
    2. Backend validates HMAC-SHA256 hash
    3. If user exists → auto-login, return JWT
    4. If user doesn't exist → auto-register + auto-login
    5. Render TMA HTML with JWT token
"""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model, login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .services import TelegramMiniAppService
from apps.accounts.services.telegram_identity import (
    TelegramIdentityUnverified,
    get_or_create_telegram_user,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auto Login / Register (API)
# ---------------------------------------------------------------------------

def _get_client_ip(request: Request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def tma_auth_view(request: Request) -> Response:
    """
    POST /api/telegram/auth/

    Telegram Mini App auth endpoint.

    Request body:
    {
        "init_data": "query_id=...&user={...}&auth_date=...&hash=..."
    }

    Response:
    {
        "success": true,
        "user": {"id": 1, "email": "...", "full_name": "..."},
        "tokens": {"access": "eyJ...", "refresh": "eyJ..."},
        "is_new_user": false
    }
    """
    from django.core.cache import cache

    # Throttle credential issuance: 10/min per IP + 20/min per init hash prefix
    ip = _get_client_ip(request)
    tkey = f"tma-auth:{ip}"
    cnt = cache.get(tkey, 0)
    if cnt >= 10:
        return Response(
            {"success": False, "error": "Juda ko'p so'rov. Bir ozdan keyin urinib ko'ring."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    cache.set(tkey, cnt + 1, timeout=60)

    init_data = request.data.get("init_data", "")
    if len(init_data) > 8192:
        return Response(
            {"success": False, "error": "initData juda uzun."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate Telegram initData
    telegram_user = TelegramMiniAppService.validate_init_data(init_data)

    if not telegram_user or not telegram_user.get("id"):
        return Response(
            {"success": False, "error": "Telegram autentifikatsiya xatoligi."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    tg_id = telegram_user["id"]
    first_name = telegram_user.get("first_name", "")
    last_name = telegram_user.get("last_name", "")

    try:
        user, is_new_user = get_or_create_telegram_user({
            "id": tg_id,
            "first_name": first_name,
            "last_name": last_name,
        })
    except TelegramIdentityUnverified as exc:
        return Response(
            {"success": False, "error": str(exc)},
            status=status.HTTP_409_CONFLICT,
        )
    except ValueError:
        return Response(
            {"success": False, "error": "Telegram ID noto'g'ri."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if is_new_user:
        logger.info("New TMA user registered: tg_id=%d, user_id=%d", tg_id, user.id)

    if not user.is_active:
        return Response(
            {"success": False, "error": "Hisob faol emas."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    # Also login via Django session (for template rendering)
    login(request, user)

    return Response({
        "success": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.get_full_name(),
            "role": user.role,
            "first_name": user.first_name,
        },
        "tokens": {
            "access": access_token,
            "refresh": refresh_token,
        },
        "is_new_user": is_new_user,
    }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# TMA Main Page
# ---------------------------------------------------------------------------

def tma_index_view(request: HttpRequest) -> HttpResponse:
    """
    GET /tma/

    Telegram Mini App main page.
    This page is opened inside Telegram's WebApp browser.
    """
    return render(request, "tma/index.html", {
        "telegram_init_data": request.GET.get("tgWebAppData", ""),
    })


# ---------------------------------------------------------------------------
# TMA Profile (requires JWT)
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tma_profile_view(request: Request) -> Response:
    """GET /api/telegram/profile/ — Current user profile for TMA."""
    user = request.user
    from apps.results.models import Result, Certificate
    from apps.games.models import UserGameScore
    from apps.essays.models import EssaySubmission

    # Quick stats
    results = Result.objects.filter(student=user)
    game_scores = UserGameScore.objects.filter(user=user)
    certificates = Certificate.objects.filter(student=user)
    essays = EssaySubmission.objects.filter(student=user)

    return Response({
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.get_full_name(),
            "role": user.role,
        },
        "stats": {
            "tests_taken": results.count(),
            "tests_passed": results.filter(is_passed=True).count(),
            "certificates": certificates.count(),
            "total_xp": sum(gs.total_xp for gs in game_scores),
            "essays_written": essays.count(),
        },
    })


# -----------------------------------------------------------------------
# TMA Arena (API) — live stats, leaderboard, pending invites
# -----------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tma_arena_view(request: Request) -> Response:
    """
    GET /api/telegram/arena/

    Combined payload for the Mini App arena screen:
        stats      — my ELO rating, W/L/D, win streak, accuracy, XP/coins
        leaderboard — top 20 players by ELO rating
        invites    — my pending custom-room invite codes
    """
    from apps.arena import services
    from apps.arena.models import ArenaProfile, ArenaRoom

    user = request.user
    profile = services.get_or_create_profile(user)
    rank = (
        ArenaProfile.objects.filter(user__is_bot=False, rating__gt=profile.rating).count()
        + 1
    )

    xp = coins = 0
    try:
        score = user.game_scores.filter(game__slug=services.ARENA_GAME_SLUG).first()
        if score:
            xp, coins = score.total_xp, score.total_coins
    except Exception:
        pass

    leaderboard = [
        {
            "rank": i + 1,
            "user_id": r.user_id,
            "name": r.user.get_full_name() or r.user.email,
            "rating": r.rating,
            "wins": r.wins,
            "losses": r.losses,
            "current_win_streak": r.current_win_streak,
            "accuracy": r.accuracy,
        }
        for i, r in enumerate(
            ArenaProfile.objects.filter(user__is_bot=False)
            .select_related("user")
            .order_by("-rating")[:20]
        )
    ]

    invites = [
        {
            "room_code": room.room_code,
            "url": f"/arena/{room.room_code}/",
        }
        for room in ArenaRoom.objects.filter(
            player1=user,
            mode=ArenaRoom.Mode.CUSTOM,
            status=ArenaRoom.Status.WAITING,
        ).order_by("-created_at")
    ]

    return Response({
        "stats": {
            "rating": profile.rating,
            "rank": rank,
            "wins": profile.wins,
            "losses": profile.losses,
            "draws": profile.draws,
            "duels_played": profile.duels_played,
            "current_win_streak": profile.current_win_streak,
            "best_win_streak": profile.best_win_streak,
            "accuracy": profile.accuracy,
            "win_rate": profile.win_rate,
            "xp": xp,
            "coins": coins,
        },
        "leaderboard": leaderboard,
        "invites": invites,
    })


# -----------------------------------------------------------------------
# TMA Tests List (API)
# -----------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tma_tests_view(request: Request) -> Response:
    """GET /api/telegram/tests/ — Available tests for TMA."""
    from apps.tests.models import Test

    tests = (
        Test.objects.filter(is_active=True)
        .select_related("course")
        .order_by("-created_at")[:20]
    )

    return Response({
        "tests": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "course": t.course.title if t.course else "",
                "time_limit_minutes": t.time_limit_minutes,
                "total_questions": t.total_questions,
                "difficulty": t.difficulty,
            }
            for t in tests
        ],
    })


# -----------------------------------------------------------------------
# TMA Results List (API)
# -----------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tma_results_view(request: Request) -> Response:
    """GET /api/telegram/results/ — User's recent results for TMA."""
    from apps.results.models import Result

    results = (
        Result.objects.filter(student=request.user)
        .select_related("test", "course")
        .order_by("-calculated_at")[:20]
    )

    return Response({
        "results": [
            {
                "id": r.id,
                "test_title": r.test.title if r.test else "",
                "course_title": r.course.title if r.course else "",
                "percentage": r.percentage,
                "is_passed": r.is_passed,
                "correct_answers": r.correct_answers,
                "total_questions": r.total_questions,
                "calculated_at": r.calculated_at.isoformat() if r.calculated_at else None,
            }
            for r in results
        ],
    })


# -----------------------------------------------------------------------
# TMA Essay Topics (API)
# -----------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tma_essay_topics_view(request: Request) -> Response:
    """GET /api/telegram/essays/topics/ — Essay topics for TMA."""
    from apps.essays.models import EssayTopic, EssaySubmission

    topics = EssayTopic.objects.filter(is_active=True).order_by("-created_at")

    # User's submissions per topic
    user_subs = {
        s.topic_id: s
        for s in EssaySubmission.objects.filter(student=request.user)
    }

    return Response({
        "topics": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "word_limit_min": t.word_limit_min,
                "word_limit_max": t.word_limit_max,
                "time_limit_minutes": t.time_limit_minutes,
                "has_password": bool(t.password),
                "user_status": (
                    {
                        "submission_id": user_subs[t.id].id,
                        "status": user_subs[t.id].status,
                        "total_score": float(user_subs[t.id].total_score) if user_subs[t.id].total_score else None,
                    }
                    if t.id in user_subs else None
                ),
            }
            for t in topics
        ],
    })


# -----------------------------------------------------------------------
# TMA Essay Submissions List (API)
# -----------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tma_essay_submissions_view(request: Request) -> Response:
    """GET /api/telegram/essays/ — User's essay submissions for TMA."""
    from apps.essays.models import EssaySubmission

    submissions = (
        EssaySubmission.objects.filter(student=request.user)
        .select_related("topic")
        .order_by("-updated_at")[:20]
    )

    return Response({
        "submissions": [
            {
                "id": s.id,
                "topic_title": s.topic.title if s.topic else "",
                "status": s.status,
                "total_score": float(s.total_score) if s.total_score else None,
                "max_score": s.max_score,
                "converted_score": s.converted_score,
                "word_count": s.word_count,
                "graded_at": s.graded_at.isoformat() if s.graded_at else None,
                "is_off_topic": s.is_off_topic,
            }
            for s in submissions
        ],
    })


# -----------------------------------------------------------------------
# TMA Essay Start (password gate + create submission)
# -----------------------------------------------------------------------

@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def tma_essay_start_view(request: Request, topic_id: int) -> Response:
    """
    POST /api/telegram/essays/{topic_id}/start/

    Start essay — verify password (if needed) and create submission.
    Request body: {"password": "..."} (optional)
    """
    from apps.essays.models import EssayTopic, EssaySubmission
    from django.utils import timezone

    try:
        topic = EssayTopic.objects.get(id=topic_id, is_active=True)
    except EssayTopic.DoesNotExist:
        return Response({"error": "Mavzu topilmadi"}, status=404)

    # Password check
    if topic.password:
        entered = request.data.get("password", "")
        if not topic.check_password(entered):
            return Response({"error": "Noto'g'ri parol"}, status=403)

    # Check existing submission — prefer a still-usable (non-expired) one.
    # Rationale: several verified submissions can exist per topic (a new one
    # is created after the previous timer expires). Picking Meta ordering
    # (-updated_at) could return an expired row touched later by autosave
    # while a usable submission exists → false 410 "Vaqt tugagan".
    candidates = (
        EssaySubmission.objects.filter(
            student=request.user, topic=topic,
            password_verified_at__isnull=False,
        )
        .order_by("-password_verified_at", "-id")
    )
    existing = None
    latest_expired = None
    for sub in candidates:
        if not sub.is_expired:
            existing = sub
            break
        if latest_expired is None:
            latest_expired = sub

    if existing is None:
        if latest_expired is not None:
            return Response(
                {"error": "Vaqt tugagan", "submission_id": latest_expired.id},
                status=410,
            )
        existing = None  # no verified submission yet → create below

    if existing:
        return Response({
            "submission_id": existing.id,
            "topic": {
                "id": topic.id,
                "title": topic.title,
                "description": topic.description,
                "word_limit_min": topic.word_limit_min,
                "word_limit_max": topic.word_limit_max,
                "time_limit_minutes": topic.time_limit_minutes,
            },
            "remaining_seconds": existing.remaining_seconds,
            "essay_text": existing.essay_text,
            "word_count": existing.word_count,
            "has_password": bool(topic.password),
        })

    # Create new submission
    submission = EssaySubmission.objects.create(
        student=request.user,
        topic=topic,
        status=EssaySubmission.Status.DRAFT,
        password_verified_at=timezone.now(),
    )

    return Response({
        "submission_id": submission.id,
        "topic": {
            "id": topic.id,
            "title": topic.title,
            "description": topic.description,
            "word_limit_min": topic.word_limit_min,
            "word_limit_max": topic.word_limit_max,
            "time_limit_minutes": topic.time_limit_minutes,
        },
        "remaining_seconds": submission.remaining_seconds,
        "essay_text": "",
        "word_count": 0,
        "has_password": bool(topic.password),
    })


# -----------------------------------------------------------------------
# TMA Essay Submit
# -----------------------------------------------------------------------

@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def tma_essay_submit_view(request: Request, submission_id: int) -> Response:
    """
    POST /api/telegram/essays/{submission_id}/submit/

    Submit essay for AI grading.
    Request body: {"essay_text": "..."}

    ASYNC contract (Cloudflare/Daphne timeout himoyasi):
        Response DARHOL qaytadi — LLM chaqiruvi Celery worker'da (yoki broker
        tushgan bo'lsa background thread'da) bajariladi. Native TMA polling
        bilan: GET /api/telegram/essays/{id}/result/ status "pending" bo'lsa
        baholash hali davom etyapti demakdir.

        202 Accepted: {"status": "processing", "submission_id": ...,
                       "poll_after": 3, "result_url": ...}
        400/410:      {"error": "..."} — validatsiya xatolari
    """
    from apps.essays.models import EssaySubmission
    from apps.essays.services import WordCounter, essay_has_grade_result, start_grading

    try:
        submission = EssaySubmission.objects.get(
            id=submission_id, student=request.user,
        )
    except EssaySubmission.DoesNotExist:
        return Response({"error": "Submission topilmadi"}, status=404)

    # Allaqachon ishlanmoqda — ikkinchi marta queue qilmaslik
    if submission.status == EssaySubmission.Status.PENDING:
        return Response(
            {
                "status": "processing",
                "submission_id": submission.id,
                "poll_after": 3,
                "result_url": f"/api/telegram/essays/{submission.id}/result/",
            },
            status=202,
        )

    # Allaqachon TO'LIQ baholangan (natija bazada) — qayta yuborish shart
    # emas; natijani ko'rsatamiz. ERROR/pending_teacher bo'lsa pastga tushib,
    # qayta baholashga yuboramiz.
    if essay_has_grade_result(submission):
        return Response(
            {
                "status": "graded",
                "submission_id": submission.id,
                "result_url": f"/api/telegram/essays/{submission.id}/result/",
            },
            status=200,
        )

    essay_text = request.data.get("essay_text", "").strip()
    if not essay_text:
        return Response({"error": "Esse matni bo'sh"}, status=400)

    # Save text (grading background'da shu matn ustida ishlaydi)
    submission.essay_text = essay_text
    submission.word_count = WordCounter.count(essay_text)

    # Time check
    if submission.password_verified_at and submission.is_expired:
        return Response({"error": "Vaqt tugagan"}, status=410)

    # Word count check
    min_words = submission.topic.word_limit_min if submission.topic else 50
    if submission.word_count < min_words:
        return Response({
            "error": f"Kamida {min_words} so'z kerak. Hozir: {submission.word_count}",
        }, status=400)

    submission.save(update_fields=["essay_text", "word_count", "updated_at"])

    # AI baholashni FONDA boshlash — broker (Celery) ishlab tursa worker'da,
    # aks holda background thread'da. Request hech qachon LLM'ni kutmaydi.
    start_grading(submission, fail_status=EssaySubmission.Status.ERROR)

    return Response(
        {
            "status": "processing",
            "submission_id": submission.id,
            "poll_after": 3,
            "result_url": f"/api/telegram/essays/{submission.id}/result/",
        },
        status=202,
    )


# -----------------------------------------------------------------------
# TMA Essay Result
# -----------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tma_essay_result_view(request: Request, submission_id: int) -> Response:
    """
    GET /api/telegram/essays/{submission_id}/result/

    Get essay grading result.
    """
    from apps.essays.models import EssaySubmission

    try:
        submission = EssaySubmission.objects.get(
            id=submission_id, student=request.user,
        )
    except EssaySubmission.DoesNotExist:
        return Response({"error": "Submission topilmadi"}, status=404)

    criteria = list(submission.criteria.all().order_by("criterion_id"))

    response = {
        "id": submission.id,
        "topic_title": submission.topic.title if submission.topic else "",
        "status": submission.status,
        "total_score": float(submission.total_score) if submission.total_score else None,
        "max_score": submission.max_score,
        "converted_score": submission.converted_score,
        "score_percentage": submission.score_percentage,
        "summary": submission.summary,
        "word_count": submission.word_count,
        "is_off_topic": submission.is_off_topic,
        "graded_at": submission.graded_at.isoformat() if submission.graded_at else None,
        "final_score": float(submission.final_score) if submission.final_score else None,
        "criteria": [
            {"id": c.criterion_id, "name": c.name, "score": float(c.score), "reason": c.reason}
            for c in criteria
        ],
    }
    # Baholash hali fonda ishlayapti (status=pending) — polling intervalini
    # client'ga aytamiz (sekundlarda).
    if submission.status == EssaySubmission.Status.PENDING:
        response["poll_after"] = 3
    return Response(response)
