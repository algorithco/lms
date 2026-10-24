from __future__ import annotations

import random
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.models import StudentGroup, Homework
from .models import VocabularyPack, StudentWordMistake
from .serializers import VocabularyPackSerializer, StudentWordMistakeSerializer
from .services.vocab_generator import (
    clean_word_list,
    generate_exercises_with_ai,
    create_vocabulary_pack,
)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_vocabulary_view(request):
    """
    Ustoz tomonidan 50-60 ta so'zdan 4 xil formatli mashq generatsiya qilish.
    """
    raw_text = request.data.get("raw_text", "").strip()
    title = request.data.get("title", "Ingliz tili Lug'at Mashqi").strip()
    group_id = request.data.get("group_id")
    save_to_db = request.data.get("save", True)

    words = clean_word_list(raw_text)
    if not words:
        return Response(
            {"error": "Kamida 1 ta so'z kiritilishi shart."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    group = None
    if group_id:
        group = get_object_or_404(StudentGroup, id=group_id)

    if save_to_db:
        pack = create_vocabulary_pack(
            raw_text=raw_text,
            title=title,
            teacher=request.user,
            group=group,
        )
        return Response(
            VocabularyPackSerializer(pack).data, status=status.HTTP_201_CREATED
        )
    else:
        exercises = generate_exercises_with_ai(words)
        return Response(
            {
                "title": title,
                "word_count": len(words),
                "exercises_data": exercises,
            }
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vocabulary_packs_list_view(request):
    """Mavjud lug'at to'plamlari ro'yxati."""
    user = request.user
    if user.is_teacher or user.is_staff:
        qs = VocabularyPack.objects.filter(teacher=user)
    else:
        # Student: uning guruhlaridagi to'plamlar
        user_groups = user.student_groups.all()
        qs = VocabularyPack.objects.filter(group__in=user_groups)

    serializer = VocabularyPackSerializer(qs[:50], many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def assign_vocabulary_homework_view(request):
    """Lug'at to'plamini guruhga vazifa (Homework) qilib biriktirish."""
    pack_id = request.data.get("pack_id")
    group_id = request.data.get("group_id")
    due_days = int(request.data.get("due_days", 3))

    pack = get_object_or_404(VocabularyPack, id=pack_id)
    group = get_object_or_404(StudentGroup, id=group_id)

    if group.teacher != request.user and not request.user.is_staff:
        return Response(
            {"error": "Faqat guruh ustozi vazifa biriktira oladi."}, status=403
        )

    deadline = timezone.now() + timezone.timedelta(days=due_days)

    homework = Homework.objects.create(
        group=group,
        title=f"Lug'at: {pack.title}",
        description=f"4 ta mashq formatini to'liq bajaring ({pack.word_count} so'z).",
        due_date=deadline,
        created_by=request.user,
    )
    pack.group = group
    pack.save(update_fields=["group"])

    return Response(
        {
            "status": "success",
            "message": f"Lug'at to'plami '{group.name}' guruhiga muvaffaqiyatli biriktirildi.",
            "homework_id": homework.id,
            "due_date": deadline.strftime("%Y-%m-%d %H:%M"),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def spaced_repetition_quiz_view(request):
    """
    O'quvchining Ebbinghaus bo'yicha adashgan 5 ta so'zidan iborat mini-viktorina.
    """
    student = request.user
    mistakes = list(
        StudentWordMistake.objects.filter(student=student, is_mastered=False).order_by(
            "-mistake_count", "next_review_at"
        )[:10]
    )

    if not mistakes:
        # Default starter words if student has no recorded mistakes
        sample_words = [
            ("resilient", "bardoshli, chidamli"),
            ("persistent", "qat'iyatli, sobitqadam"),
            ("meticulous", "o'ta ehtiyotkor, sinchkov"),
            ("lucid", "aniq, tushunarli"),
            ("empathy", "hamdardlik"),
        ]
        questions = []
        for idx, (w, m) in enumerate(sample_words):
            distractors = ["dangasa", "qo'pol", "shoshqaloq", "noto'g'ri fikr"]
            opts = [m] + random.sample(distractors, 3)
            random.shuffle(opts)
            questions.append(
                {
                    "id": idx + 1,
                    "word": w,
                    "question": f"'{w}' so'zining to'g'ri o'zbekcha tarjimasi qaysi?",
                    "options": opts,
                    "correct_answer": m,
                    "streak": 0,
                }
            )
        return Response(
            {
                "status": "sample",
                "message": "Hozircha xatolar yo'q. Mashg'ulot uchun namunaviy viktorina:",
                "questions": questions,
            }
        )

    selected = random.sample(mistakes, min(5, len(mistakes)))
    questions = []
    for item in selected:
        meaning = item.translation_uz or item.definition or "To'g'ri tarjima"
        distractors = [
            "tezkor qaror",
            "qoniqarsiz natija",
            "noma'lum xulosa",
            "qarama-qarshi holat",
        ]
        opts = [meaning] + random.sample(distractors, 3)
        random.shuffle(opts)
        questions.append(
            {
                "id": item.id,
                "word": item.word,
                "question": f"'{item.word}' so'zining ma'nosi qaysi?",
                "options": opts,
                "correct_answer": meaning,
                "streak": item.consecutive_correct_streak,
                "mistake_count": item.mistake_count,
            }
        )

    return Response(
        {
            "status": "active",
            "total_active_mistakes": len(mistakes),
            "questions": questions,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def spaced_repetition_submit_view(request):
    """
    O'quvchining so'z viktorinasidagi javobini qayd etish.
    3 marta to'g'ri topsa 'is_mastered = True' bo'ladi.
    """
    word = request.data.get("word", "").strip()
    is_correct = bool(request.data.get("is_correct", False))
    translation_uz = request.data.get("translation_uz", "")
    definition = request.data.get("definition", "")

    if not word:
        return Response({"error": "So'z ko'rsatilishi shart."}, status=400)

    mistake, _ = StudentWordMistake.objects.get_or_create(
        student=request.user,
        word=word.lower(),
        defaults={"translation_uz": translation_uz, "definition": definition},
    )
    if translation_uz and not mistake.translation_uz:
        mistake.translation_uz = translation_uz
    if definition and not mistake.definition:
        mistake.definition = definition

    newly_mastered = mistake.record_attempt(is_correct)

    return Response(
        {
            "status": "success",
            "word": mistake.word,
            "is_correct": is_correct,
            "streak": mistake.consecutive_correct_streak,
            "is_mastered": mistake.is_mastered,
            "newly_mastered": newly_mastered,
            "message": (
                "🎉 Tabriklaymiz! Siz ushbu so'zni to'liq yod oldingiz!"
                if newly_mastered
                else f"Natija qayd etildi. Joriy to'g'ri seriya: {mistake.consecutive_correct_streak}/3"
            ),
        }
    )
