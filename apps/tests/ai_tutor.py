"""
24/7 Shaxsiy AI Repetitor va Xatolar Diagnostikasi.

1. Test natijasi bo'yicha zaif mavzular tahlili (Morfologiya, Sintaksis, Adabiy davrlar va h.k.)
2. Har bir xato savol uchun interaktiv tushuntirish:
   - Nega tanlangan javob xato?
   - To'g'ri javobning qoidasi va asosi
   - Eslab qolish uchun maslahat (Memory tip)
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache

from apps.results.models import Result
from apps.tests.models import Choice, Question

logger = logging.getLogger(__name__)

# Ona tili va adabiyoti bo'yicha standart mavzular kalit so'zlari
TOPIC_KEYWORDS = {
    "Fonetika va imlo": [
        "tovush",
        "harf",
        "unli",
        "undosh",
        "urg'u",
        "bo'g'in",
        "tuturuq",
        "imlo",
        "talaffuz",
        "singarmonizm",
        "jarangli",
        "jarangsiz",
    ],
    "Leksikologiya va frazeologiya": [
        "ma'no",
        "sinonim",
        "antonim",
        "omonim",
        "paronim",
        "iboralar",
        "ibora",
        "frazeologizm",
        "ko'chma",
        "o'z ma'no",
        "sheva",
        "atamalar",
    ],
    "Morfologiya (So'z turkumlari)": [
        "ot",
        "sifat",
        "son",
        "olmosh",
        "fe'l",
        "ravish",
        "ko'makchi",
        "bog'lovchi",
        "yuklama",
        "qo'shimcha",
        "shakl yasovchi",
        "so'z yasovchi",
        "zamon",
        "mayl",
        "nisbat",
        "daraja",
        "egalik",
        "kelishik",
    ],
    "Sintaksis va tinish belgilari": [
        "gap",
        "soddagap",
        "qo'shmagap",
        "ergashgan",
        "bosh gap",
        "ega",
        "kesim",
        "to'ldiruvchi",
        "aniqlovchi",
        "hol",
        "uyushiq",
        "tinish belgisi",
        "vergul",
        "nuqta",
        "tire",
        "ikki nuqta",
        "kirish so'z",
        "undalma",
    ],
    "Mumtoz adabiyot": [
        "navoiy",
        "bobur",
        "lutfiy",
        "yassaviy",
        "mashrab",
        "furqat",
        "muqimiy",
        "ogahiy",
        "g'azal",
        "ruboiy",
        "qasida",
        "masnaviy",
        "tuyuq",
        "aruz",
        "vazn",
        "bahr",
        "devon",
        "xamsa",
    ],
    "Jadid va zamonaviy adabiyot": [
        "behbudiy",
        "fitrat",
        "cho'lpon",
        "qodiriy",
        "avloniy",
        "oybek",
        "g'afur g'ulom",
        "abdulla oripov",
        "erkin vohidov",
        "o'tkir hoshimov",
        "roman",
        "qissa",
        "hikoya",
        "drama",
        "jadid",
    ],
    "Matn tahlili va uslubiyat": [
        "matn",
        "parcha",
        "uslub",
        "badiiy",
        "ilmiy",
        "publitsistik",
        "so'zlashuv",
        "g'oya",
        "mavzu",
        "xulosa",
        "muallif maqsadi",
    ],
}


def _detect_question_topic(question_text: str, explanation: str = "") -> str:
    """Savol matni va izohiga qarab mavzuni aniqlaydi."""
    combined = f"{question_text} {explanation}".lower()
    scores: dict[str, int] = {}
    for topic, words in TOPIC_KEYWORDS.items():
        score = sum(1 for w in words if w in combined)
        if score > 0:
            scores[topic] = score

    if scores:
        return max(scores.items(), key=lambda x: x[1])[0]
    return "Umumiy ona tili va adabiyot qoidalari"


def get_result_diagnostics(result_id: int) -> dict[str, Any]:
    """
    Test natijasi bo'yicha AI diagnostikasini yaratadi yoki keshdan qaytaradi.
    """
    cache_key = f"ai_tutor_diagnostics_r{result_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    result = (
        Result.objects.filter(id=result_id)
        .select_related("attempt", "test", "student")
        .first()
    )
    if not result:
        return {"error": "Natija topilmadi."}

    attempt = result.attempt
    answers = list(
        attempt.answers.select_related("question").prefetch_related(
            "selected_choices", "question__choices"
        )
    )

    wrong_by_topic: dict[str, list[dict]] = {}
    correct_count = 0

    for ans in answers:
        if ans.is_correct is False or (
            ans.is_correct is None and not ans.selected_choices.exists()
        ):
            q = ans.question
            topic = _detect_question_topic(q.text, q.explanation)
            if topic not in wrong_by_topic:
                wrong_by_topic[topic] = []

            selected_text = (
                ", ".join(c.text for c in ans.selected_choices.all())
                or "(Javob berilmagan)"
            )
            correct_choice = q.choices.filter(is_correct=True).first()
            correct_text = (
                correct_choice.text if correct_choice else "(Kalit ko'rsatilmagan)"
            )

            wrong_by_topic[topic].append(
                {
                    "question_id": q.id,
                    "position": q.position,
                    "question_text": q.text,
                    "selected_answer": selected_text,
                    "correct_answer": correct_text,
                }
            )
        elif ans.is_correct is True:
            correct_count += 1

    # Zaif mavzular reytingi
    weak_topics = []
    for topic, questions in sorted(
        wrong_by_topic.items(), key=lambda x: len(x[1]), reverse=True
    ):
        count = len(questions)
        weak_topics.append(
            {
                "topic": topic,
                "error_count": count,
                "questions": questions,
                "advice": _get_topic_advice(topic),
            }
        )

    # Shaxsiy tavsiyalar
    recommendations = []
    if weak_topics:
        top_weak = weak_topics[0]["topic"]
        recommendations.append(
            f"Eng ko'p xato: '{top_weak}'. Ushbu mavzudagi qoidalarni darslikdan qayta takrorlang."
        )
        if len(weak_topics) > 1:
            recommendations.append(
                f"Qo'shimcha e'tibor qarating: '{weak_topics[1]['topic']}'."
            )
        recommendations.append(
            "BMB darajangizni oshirish uchun har kuni kamida 1 ta mavzulashtirilgan test ishlang."
        )
    else:
        recommendations.append(
            "Ajoyib natija! Xatolar deyarli yo'q. Esse yozish va murakkab matn tahliliga e'tibor bering."
        )

    # Umumiy xulosa
    pct = float(result.percentage)
    if pct >= 86:
        summary = "Siz Milliy sertifikatning eng yuqori A+ darajasiga loyiq bilimlarni namoyon qildingiz! Barcha mavzularda yuqori barqarorlik mavjud."
    elif pct >= 68:
        summary = "Yaxshi natija (B/B+ darajasi). Asosiy nazariy bilimlar mavjud, biroq ayrim nozik qoidalarda xatoliklar uchramoqda. Zaif mavzularni mustahkamlasangiz, A darajasiga chiqasiz."
    else:
        summary = "Hozircha natija yetarli emas. Morfologiya va sintaksis qoidalarini bosqichma-bosqich takrorlashni tavsiya qilamiz."

    diagnostics = {
        "result_id": result.id,
        "student_name": result.student.get_full_name() or result.student.email,
        "percentage": pct,
        "bmb_grade": result.bmb_grade,
        "total_questions": result.total_questions,
        "correct_answers": result.correct_answers,
        "wrong_answers": result.wrong_answers,
        "weak_topics": weak_topics,
        "recommendations": recommendations,
        "summary": summary,
    }

    cache.set(cache_key, diagnostics, timeout=3600 * 24)
    return diagnostics


def _get_topic_advice(topic: str) -> str:
    """Mavzu bo'yicha tezkor repetitor maslahati."""
    advice_map = {
        "Fonetika va imlo": "Qo'sh unlilar, tuturuq belgisi va jarangli/jarangsiz undoshlar imlosiga oid qoidalarni 5-sinf darsligidan takrorlang.",
        "Leksikologiya va frazeologiya": "Frazeologik lug'at va o'zbek tilining izohli lug'ati bilan ishlang, ko'chma ma'noli iboralarni yod oling.",
        "Morfologiya (So'z turkumlari)": "Mustaqil va yordamchi so'z turkumlari, kelishik va qo'shimchalar vazifasini jadval asosida ko'rib chiqing.",
        "Sintaksis va tinish belgilari": "Ergashgan qo'shma gaplarning turlari (aniqlovchi, to'ldiruvchi, hol) va ularda vergul qo'yilish qoidalarini mustahkamlang.",
        "Mumtoz adabiyot": "Alisher Navoiy 'Xamsa' dostonlari va g'azallari, aruz vazni turlari (hazaj, ramal) hamda mumtoz san'atlarni o'rganing.",
        "Jadid va zamonaviy adabiyot": "Abdulla Qodiriy va Cho'lpon asarlarining yaratilish tarixi, bosh qahramonlari tahliliga e'tibor qarating.",
        "Matn tahlili va uslubiyat": "Matnni diqqat bilan o'qib, muallif g'oyasi va kalit so'zlarni ajratish malakasini oshiring.",
    }
    return advice_map.get(
        topic, "Ushbu mavzu bo'yicha darslik va amaliy mashqlarni bajaring."
    )


def explain_question_mistake(
    question_id: int,
    selected_choice_id: int | None = None,
    attempt_id: int | None = None,
) -> dict[str, Any]:
    """
    Har bir xato ishlangan savol uchun 24/7 AI tushuntirishini qaytaradi:
      - Nega tanlangan javob xato?
      - Qaysi qoida asosida to'g'ri javob to'g'ri?
      - Eslab qolish uchun mnemonik qoida / maslahat
    """
    cache_key = f"ai_explain_q{question_id}_c{selected_choice_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    question = (
        Question.objects.filter(id=question_id).prefetch_related("choices").first()
    )
    if not question:
        return {"error": "Savol topilmadi."}

    correct_choice = question.choices.filter(is_correct=True).first()
    selected_choice = (
        question.choices.filter(id=selected_choice_id).first()
        if selected_choice_id
        else None
    )

    # Agar o'quvchi javobi attempt orqali olinayotgan bo'lsa
    ans = None
    if attempt_id:
        from apps.tests.models import StudentAnswer

        ans = StudentAnswer.objects.filter(
            attempt_id=attempt_id, question_id=question_id
        ).first()
        if not selected_choice and ans:
            selected_choice = ans.selected_choices.first()

    correct_text = correct_choice.text if correct_choice else "Kalit variant"
    selected_text = selected_choice.text if selected_choice else "Javob belgilanmagan"

    # 0. English exam or passage evidence extraction
    passage_text = ""
    if getattr(question, "reading_passage", None):
        passage_text = question.reading_passage.content
    elif getattr(question, "passage", None):
        passage_text = question.passage

    test_obj = getattr(question, "test", None)
    is_english = (
        getattr(test_obj, "subject", "") == "english"
        or getattr(test_obj, "exam_type", "")
        in ["ielts_academic", "ielts_general", "cefr_multilevel"]
        or bool(passage_text)
    )

    if is_english:
        from apps.tests.evidence_feedback import generate_reading_listening_evidence

        evidence = generate_reading_listening_evidence(
            question_text=question.text,
            selected_answer=selected_text,
            correct_answer=correct_text,
            passage_text=passage_text,
            question_explanation=question.explanation or "",
        )
        explanation_data = {
            "question_id": question.id,
            "topic": "English Examination",
            "question_text": question.text,
            "selected_answer": selected_text,
            "correct_answer": correct_text,
            "direct_quote": evidence.get("direct_quote", ""),
            "why_wrong": evidence.get("why_wrong", ""),
            "synonym_matching": evidence.get("synonym_matching", ""),
            "correct_rule": evidence.get("correct_rule", ""),
            "memory_tip": evidence.get("correct_rule", ""),
            "full_explanation": (
                f"📌 Dalil (Direct Quote):\n{evidence.get('direct_quote', '')}\n\n"
                f"💡 Nega noto'g'ri (Why Wrong):\n{evidence.get('why_wrong', '')}\n\n"
                f"🎯 Kalit so'zlar / Sinonimlar:\n{evidence.get('synonym_matching', '')}\n\n"
                f"✅ Asos: {evidence.get('correct_rule', '')}"
            ),
            "source": evidence.get("source", "evidence_engine"),
        }
        if ans:
            ans.ai_feedback = explanation_data
            ans.save(update_fields=["ai_feedback"])
        cache.set(cache_key, explanation_data, timeout=3600 * 24 * 7)
        return explanation_data

    # Mavzuni aniqlash
    topic = _detect_question_topic(question.text, question.explanation)

    # 1. Agar LLM mavjud bo'lsa, aqlli izoh generatsiya qilish
    explanation_data = None
    try:
        from apps.essays.services import (
            _get_llm_client,
            _is_mock_mode,
            _chat_with_fallback,
            _model_candidates,
        )

        if not _is_mock_mode():
            client = _get_llm_client(timeout=15.0)
            candidates = _model_candidates()

            prompt = (
                f"Sen ona tili va adabiyotidan Milliy sertifikat repetitorisan.\n"
                f"Savol: {question.text}\n"
                f"Mavzu: {topic}\n"
                f"O'quvchi tanlagan NOTO'G'RI javob: {selected_text}\n"
                f"TO'G'RI javob: {correct_text}\n"
                f"Mavjud izoh: {question.explanation}\n\n"
                f"Quyidagi 3 ta band bo'yicha qisqa, aniq va tushunarli o'zbek tilida tushuntir:\n"
                f"1. NEGA XATO: O'quvchi nega adashdi va nega uning javobi noto'g'ri?\n"
                f"2. QOIDA: To'g'ri javobni isbotlovchi aniq grammatik/adabiy qoida.\n"
                f"3. ESLAB QOLISH UCHUN: Keyingi safar adashmaslik uchun qisqa qoida yoki mnemonika."
            )

            response, _ = _chat_with_fallback(
                client,
                candidates[0],
                candidates[1:],
                messages=[
                    {
                        "role": "system",
                        "content": "Sen o'zbek tili va adabiyoti bo'yicha mehribon, tajribali repetitorsan. Javoblaringni ixcham, qat'iy faktlar asosida yoz.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
                temperature=0.3,
            )
            llm_text = (response.choices[0].message.content or "").strip()
            if llm_text:
                explanation_data = {
                    "question_id": question.id,
                    "topic": topic,
                    "question_text": question.text,
                    "selected_answer": selected_text,
                    "correct_answer": correct_text,
                    "full_explanation": llm_text,
                    "why_wrong": f"'{selected_text}' varianti ushbu savol shartiga mos kelmaydi.",
                    "correct_rule": f"To'g'ri javob — '{correct_text}'. {question.explanation or _get_topic_advice(topic)}",
                    "memory_tip": f"Eslab qoling: {topic} bo'yicha qoidani qayta takrorlang.",
                    "source": "ai",
                }
    except Exception as e:
        logger.warning("LLM explain question failed: %s", e)

    # Fallback deterministik repetitor javobi
    if not explanation_data:
        explanation_data = {
            "question_id": question.id,
            "topic": topic,
            "question_text": question.text,
            "selected_answer": selected_text,
            "correct_answer": correct_text,
            "why_wrong": (
                f"Siz tanlagan '{selected_text}' varianti noto'g'ri. "
                f"Ushbu javob kontekst mazmuniga yoki morfologik/sintaktik qoidalarga zid keladi."
            ),
            "correct_rule": (
                f"To'g'ri javob — '{correct_text}'. "
                f"{question.explanation if question.explanation else _get_topic_advice(topic)}"
            ),
            "memory_tip": (
                f"💡 Kalit qoida: '{topic}' mavzusida doimo so'z ma'nosi va grammatik bog'lanishlarga e'tibor bering."
            ),
            "source": "rule_engine",
        }

    cache.set(cache_key, explanation_data, timeout=3600 * 24 * 7)
    return explanation_data
