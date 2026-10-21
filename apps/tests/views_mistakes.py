"""
Adaptive Re-Test Engine & Mistakes Workbench ("Xatolar ustida avto-mashq").

O'quvchi test topshirgach, uning xatolari shunchaki qolib ketmaydi:
1. /api/v1/tests/attempts/<id>/generate-retest/ — xato savollardan va zaif mavzulardan iborat
   maqsadli yangi mini-test va attempt yaratadi.
2. /api/v1/tests/mistake-vault/ — o'quvchining zaif nuqtalari va o'zlashtirilgan xatolari statistikasi.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tests.ai_tutor import _detect_question_topic
from apps.tests.models import Choice, Question, StudentAnswer, Test, TestAttempt

logger = logging.getLogger(__name__)


class GenerateRetestView(APIView):
    """
    POST /api/v1/tests/attempts/<attempt_id>/generate-retest/
    POST /api/tests/attempts/<attempt_id>/generate-retest/

    Talabaning ushbu urinishdagi barcha xato ishlangan savollari va zaif mavzulari
    asosida moslashtirilgan "Xatolar ustida mashq" testini yaratadi va attemptni ochadi.
    """

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request: Request, attempt_id: int) -> Response:
        attempt = TestAttempt.objects.filter(pk=attempt_id).first()
        if not attempt:
            from apps.results.models import Result

            res_obj = Result.objects.filter(pk=attempt_id).first()
            if res_obj:
                attempt = res_obj.attempt

        if not attempt:
            return Response(
                {"error": "Urinish topilmadi."}, status=status.HTTP_404_NOT_FOUND
            )

        # Xavfsizlik: faqat o'quvchining o'zi yoki admin
        if (
            attempt.student_id != request.user.id
            and not request.user.is_staff
            and getattr(request.user, "role", None) != "admin"
        ):
            return Response(
                {
                    "error": "Siz faqat o'z urinishlaringiz bo'yicha qayta test generatsiya qila olasiz."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Xato javoblarni qidirish
        wrong_answers = (
            StudentAnswer.objects.filter(attempt=attempt, is_correct=False)
            .select_related("question")
            .prefetch_related("question__choices")
        )

        wrong_questions = [a.question for a in wrong_answers if a.question]

        if not wrong_questions:
            return Response(
                {
                    "has_mistakes": False,
                    "message": "Tabriklaymiz! Siz ushbu testdagi barcha savollarni to'g'ri yechgansiz. Qayta mashq talab etilmaydi.",
                },
                status=status.HTTP_200_OK,
            )

        orig_test = attempt.test
        weak_topics = set()
        for q in wrong_questions:
            t = _detect_question_topic(q.text, q.explanation)
            weak_topics.add(t)

        # Savollar ro'yxatini shakllantirish (kamida 5 ta bo'lishi uchun tegishli mavzulardan qo'shimcha savollar)
        selected_questions = list(wrong_questions)

        if len(selected_questions) < 5 and orig_test:
            # Shu kurs yoki fanning boshqa savollaridan qo'shish
            extra_qs = (
                Question.objects.filter(test__subject=orig_test.subject)
                .exclude(id__in=[q.id for q in selected_questions])
                .prefetch_related("choices")[: 5 - len(selected_questions)]
            )
            selected_questions.extend(list(extra_qs))

        # Yangi maqsadli mashq Testini yaratish
        retest_title = f"Xatolar ustida mashq: {orig_test.title}"
        if len(retest_title) > 250:
            retest_title = retest_title[:247] + "..."

        retest = Test.objects.create(
            course=orig_test.course,
            subject=orig_test.subject,
            title=retest_title,
            description=f"'{orig_test.title}' testida xato qilingan mavzular bo'yicha maxsus tuzilgan mashq.",
            time_limit_minutes=max(10, len(selected_questions) * 2),
            pass_percentage=70,
            difficulty=orig_test.difficulty,
            status=Test.Status.PUBLISHED,
            is_active=True,
            shuffle_choices=False,
        )

        # Savollarni klonlash
        for pos, src_q in enumerate(selected_questions, start=1):
            cloned_q = Question.objects.create(
                test=retest,
                text=src_q.text,
                reading_passage=src_q.reading_passage,
                passage=src_q.passage,
                question_type=src_q.question_type,
                points=src_q.points or 1,
                explanation=src_q.explanation
                or "Ushbu savol o'tgan testdagi xato bo'yicha mustahkamlash uchun berildi.",
                position=pos,
            )
            for c in src_q.choices.all():
                Choice.objects.create(
                    question=cloned_q,
                    text=c.text,
                    is_correct=c.is_correct,
                    position=c.position,
                )

        # Yangi TestAttempt ochish
        new_attempt = TestAttempt.objects.create(
            test=retest,
            student=request.user,
            status=TestAttempt.Status.IN_PROGRESS,
        )

        return Response(
            {
                "has_mistakes": True,
                "retest_test_id": retest.id,
                "attempt_id": new_attempt.id,
                "total_questions": len(selected_questions),
                "weak_topics": list(weak_topics),
                "message": f"Xatolaringiz bo'yicha {len(selected_questions)} ta savoldan iborat yangi mashq yaratildi!",
            },
            status=status.HTTP_201_CREATED,
        )


class MistakeVaultView(APIView):
    """
    GET /api/v1/tests/mistake-vault/
    GET /api/tests/mistake-vault/

    O'quvchining barcha o'tgan testlardagi xatoliklari, zaif nuqtalari
    va o'zlashtirish darajasini monitoring qilish.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        student = request.user
        wrong_answers = (
            StudentAnswer.objects.filter(attempt__student=student, is_correct=False)
            .select_related("question", "attempt__test")
            .order_by("-answered_at")[:100]
        )

        topic_counts: dict[str, int] = {}
        recent_mistakes: list[dict[str, Any]] = []

        seen_q = set()
        for a in wrong_answers:
            if not a.question or a.question.id in seen_q:
                continue
            seen_q.add(a.question.id)
            topic = _detect_question_topic(a.question.text, a.question.explanation)
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

            correct_choice = a.question.choices.filter(is_correct=True).first()
            if len(recent_mistakes) < 10:
                recent_mistakes.append(
                    {
                        "question_id": a.question.id,
                        "question_text": a.question.text,
                        "topic": topic,
                        "test_title": a.attempt.test.title
                        if a.attempt and a.attempt.test
                        else "Test",
                        "correct_answer": correct_choice.text
                        if correct_choice
                        else "Kalit",
                        "explanation": a.question.explanation,
                        "date": a.answered_at,
                    }
                )

        # To'g'ri ishlangan (o'zlashtirilgan) savollar soni
        correct_count = (
            StudentAnswer.objects.filter(attempt__student=student, is_correct=True)
            .values("question_id")
            .distinct()
            .count()
        )

        weak_topics_list = [
            {"topic": k, "error_count": v}
            for k, v in sorted(
                topic_counts.items(), key=lambda item: item[1], reverse=True
            )
        ]

        return Response(
            {
                "unresolved_count": len(seen_q),
                "mastered_count": correct_count,
                "weak_topics": weak_topics_list,
                "recent_mistakes": recent_mistakes,
            },
            status=status.HTTP_200_OK,
        )
