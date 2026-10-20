"""
Speaking app views (apps/speaking/views.py).

Endpoints:
    GET  /api/v1/speaking/topics/            — List active IELTS/Multi-level topics
    GET  /api/v1/speaking/topics/<id>/       — Topic detail with Cue Card bullets
    POST /api/v1/speaking/submit/            — Upload audio, get instant 4-criteria AI evaluation
    GET  /api/v1/speaking/submissions/<id>/  — Detailed score card & feedback
    GET  /api/v1/speaking/my-submissions/    — User history
"""

from __future__ import annotations

import logging
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SpeakingSubmission, SpeakingTopic
from .services import evaluate_speaking_submission

logger = logging.getLogger(__name__)


def _serialize_topic(topic: SpeakingTopic) -> dict:
    return {
        "id": topic.id,
        "title": topic.title,
        "subject": topic.subject,
        "part": topic.part,
        "part_label": topic.get_part_display(),
        "prompt": topic.prompt,
        "bullet_points": topic.bullet_points,
        "follow_up_questions": topic.follow_up_questions,
        "prep_time_seconds": topic.prep_time_seconds,
        "speak_time_seconds": topic.speak_time_seconds,
        "difficulty": topic.difficulty,
        "difficulty_label": topic.get_difficulty_display(),
    }


def _serialize_submission(sub: SpeakingSubmission) -> dict:
    return {
        "id": sub.id,
        "topic_id": sub.topic_id,
        "topic_title": sub.topic.title if sub.topic else "",
        "part": sub.topic.part if sub.topic else "",
        "part_label": sub.topic.get_part_display() if sub.topic else "",
        "audio_url": sub.audio_file.url if sub.audio_file else None,
        "duration_seconds": sub.duration_seconds,
        "transcript": sub.transcript,
        "fluency_score": float(sub.fluency_score),
        "lexical_score": float(sub.lexical_score),
        "grammar_score": float(sub.grammar_score),
        "pronunciation_score": float(sub.pronunciation_score),
        "overall_band": float(sub.overall_band),
        "feedback": sub.feedback,
        "status": sub.status,
        "created_at": sub.created_at.isoformat(),
    }


class SpeakingTopicsListView(APIView):
    """GET /api/v1/speaking/topics/"""

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        qs = SpeakingTopic.objects.filter(is_active=True)
        part = request.query_params.get("part", "").strip()
        if part:
            qs = qs.filter(part=part)

        # Seed standard IELTS speaking topics if empty
        if not qs.exists() and not SpeakingTopic.objects.exists():
            _seed_default_speaking_topics()
            qs = SpeakingTopic.objects.filter(is_active=True)
            if part:
                qs = qs.filter(part=part)

        data = [_serialize_topic(t) for t in qs]
        return Response(
            {"count": len(data), "results": data}, status=status.HTTP_200_OK
        )


class SpeakingTopicDetailView(APIView):
    """GET /api/v1/speaking/topics/<id>/"""

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request, pk: int) -> Response:
        topic = SpeakingTopic.objects.filter(pk=pk, is_active=True).first()
        if not topic:
            return Response(
                {"error": "Speaking mavzusi topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(_serialize_topic(topic), status=status.HTTP_200_OK)


class SpeakingSubmitView(APIView):
    """
    POST /api/v1/speaking/submit/
    Multipart form-data: `audio`, `topic_id`, optional `duration_seconds`.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request) -> Response:
        audio_file = request.FILES.get("audio")
        if not audio_file:
            return Response(
                {"ok": False, "error": "Ovoz yozuvi (audio) yuklanmadi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        topic_id_raw = request.data.get("topic_id")
        if not topic_id_raw or not str(topic_id_raw).isdigit():
            return Response(
                {"ok": False, "error": "Mavzu ID si (topic_id) ko'rsatilmadi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        topic_id = int(topic_id_raw)

        duration_raw = request.data.get("duration_seconds", "60")
        duration = int(duration_raw) if str(duration_raw).isdigit() else 60

        try:
            sub = evaluate_speaking_submission(
                audio_file=audio_file,
                topic_id=topic_id,
                user=request.user,
                duration_seconds=duration,
            )
            return Response(
                {"ok": True, "submission": _serialize_submission(sub)},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            logger.exception("Speaking evaluation failed: %s", e)
            return Response(
                {"ok": False, "error": f"Baholashda xatolik yuz berdi: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SpeakingSubmissionDetailView(APIView):
    """GET /api/v1/speaking/submissions/<id>/"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, pk: int) -> Response:
        sub = SpeakingSubmission.objects.filter(pk=pk, user=request.user).first()
        if not sub and request.user.role in ("teacher", "admin"):
            sub = SpeakingSubmission.objects.filter(pk=pk).first()

        if not sub:
            return Response(
                {"error": "Topshiriq topilmadi."}, status=status.HTTP_404_NOT_FOUND
            )

        return Response(_serialize_submission(sub), status=status.HTTP_200_OK)


class MySpeakingSubmissionsView(APIView):
    """GET /api/v1/speaking/my-submissions/"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        subs = (
            SpeakingSubmission.objects.filter(user=request.user)
            .select_related("topic")
            .order_by("-created_at")[:20]
        )
        data = [_serialize_submission(s) for s in subs]
        return Response(
            {"count": len(data), "results": data}, status=status.HTTP_200_OK
        )


def _seed_default_speaking_topics():
    """Initial seed topics for IELTS Part 1, Part 2 (Cue Card), and Part 3."""
    SpeakingTopic.objects.get_or_create(
        title="Hometown & Daily Life",
        part=SpeakingTopic.PartChoice.PART1,
        defaults={
            "prompt": "Let's talk about your hometown. Where is it located? What do you like most about living there? Would you like to live there in the future?",
            "bullet_points": [
                "Where your hometown is located",
                "What its best features are",
                "How it has changed recently",
            ],
            "prep_time_seconds": 15,
            "speak_time_seconds": 60,
            "difficulty": SpeakingTopic.Difficulty.EASY,
        },
    )
    SpeakingTopic.objects.get_or_create(
        title="Describe an Influential Book You Have Read",
        part=SpeakingTopic.PartChoice.PART2,
        defaults={
            "prompt": "Describe a book that has had a powerful influence on your thinking or life choices.",
            "bullet_points": [
                "What the book is and who wrote it",
                "What the main message or story is",
                "When and why you read it",
                "Explain why it had such a strong impact on you",
            ],
            "prep_time_seconds": 60,
            "speak_time_seconds": 120,
            "difficulty": SpeakingTopic.Difficulty.MEDIUM,
        },
    )
    SpeakingTopic.objects.get_or_create(
        title="Describe an Important Decision You Made",
        part=SpeakingTopic.PartChoice.PART2,
        defaults={
            "prompt": "Describe an important choice or life decision you made in the past few years.",
            "bullet_points": [
                "What the decision was",
                "When you had to make it",
                "How you felt while deciding",
                "Explain whether it turned out to be the right decision",
            ],
            "prep_time_seconds": 60,
            "speak_time_seconds": 120,
            "difficulty": SpeakingTopic.Difficulty.MEDIUM,
        },
    )
    SpeakingTopic.objects.get_or_create(
        title="Artificial Intelligence & Future Education",
        part=SpeakingTopic.PartChoice.PART3,
        defaults={
            "prompt": "How do you think emerging AI tools will reshape traditional classroom learning over the next decade? Can AI ever replace empathetic human educators?",
            "follow_up_questions": [
                "Do teachers still remain essential in the age of generative AI?",
                "How can schools ensure digital literacy for underprivileged students?",
            ],
            "prep_time_seconds": 15,
            "speak_time_seconds": 90,
            "difficulty": SpeakingTopic.Difficulty.HARD,
        },
    )
