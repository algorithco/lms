"""
AI Document Converter — PDF va rasmli testlardan interaktiv test yaratuvchi Vision AI xizmati.

Ustoz kitob sahifasi rasmini yoki test PDF faylini yuklaydi:
1. Matnli PDF bo'lsa: pypdf orqali matn ajratib olinadi va LLM'ga uzatiladi.
2. Rasmli PDF yoki foto (PNG, JPEG) bo'lsa: Gemini Vision yoki OpenRouter Vision orqali tahlil qilinadi.
3. Structured JSON formatida savollar, variantlar va to'g'ri javoblar qaytariladi.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from typing import Any

from django.conf import settings
from django.db import transaction

from apps.courses.models import Course
from apps.tests.mock_service import (
    _get_or_create_mock_course,
    generate_unique_mock_code,
)
from apps.tests.models import Choice, Question, ReadingPassage, Test

logger = logging.getLogger(__name__)


PROMPT_SYSTEM = (
    "Sen O'zbekistondagi eng tajribali Milliy sertifikat va IELTS/CEFR test tuzuvchi ekspertisan. "
    "Sening vazifang berilgan test hujjati, rasmi yoki matnidan barcha savollar, variantlar va to'g'ri javoblarni "
    "aniq ajratib olib, qat'iy JSON formatida qaytarishdir."
)

PROMPT_JSON_INSTRUCTIONS = """
Qoidalar:
1. Agar hujjatda bir nechta savolga tegishli umumiy matn (Reading passage) bo'lsa, uni "reading_passage"ga kirit.
2. Har bir savol matnini "text" maydoniga yoz.
3. Variantlarni A, B, C, D harflari bilan "choices" massivida qaytar. Format: [{"code": "A", "text": "..."}, {"code": "B", "text": "..."}].
4. To'g'ri javob kaliti ko'rsatilgan bo'lsa (masalan: 1-B yoki belgilangan bo'lsa), "correct_answer": "B" qilib belgilang.
   Agar hujjatda to'g'ri javob belgilanmagan bo'lsa, o'zing to'g'ri javobni aniqlab "correct_answer"ga yoz va "explanation"ga qisqa qoidani kirit.
5. Savol turini ("single_choice", "multiple_choice", "text") belgilang.

Faqat va faqat quyidagi toza JSON formatni qaytar (hech qanday markdown prefikslarsiz):
{
  "test_title": "Olingan sarlavha",
  "reading_passage": "Agar umumiy matn bo'lsa matn, aks holda bo'sh satr",
  "questions": [
    {
      "order": 1,
      "text": "Savol matni",
      "choices": [
        {"code": "A", "text": "Variant A"},
        {"code": "B", "text": "Variant B"},
        {"code": "C", "text": "Variant C"},
        {"code": "D", "text": "Variant D"}
      ],
      "correct_answer": "A",
      "explanation": "To'g'ri javob qoidasi yoki izohi",
      "question_type": "single_choice"
    }
  ]
}
"""


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    """PDF fayldan raqamli matnni pypdf orqali ajratib olish."""
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        extracted = []
        for page in reader.pages[:10]:  # Bir urinishda 10 sahifagacha
            t = page.extract_text() or ""
            if t.strip():
                extracted.append(t.strip())
        return "\n\n".join(extracted).strip()
    except Exception as e:
        logger.warning("PDF matnini ajratishda xatolik: %s", e)
        return ""


def _call_gemini_vision(image_bytes: bytes, mime_type: str, prompt: str) -> str:
    """Gemini API orqali rasmni tahlil qilish."""
    api_key = getattr(settings, "GEMINI_API_KEY", "") or getattr(
        settings, "GOOGLE_API_KEY", ""
    )
    if not api_key:
        return ""

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        image_part = {
            "mime_type": mime_type,
            "data": image_bytes,
        }

        response = model.generate_content(
            [PROMPT_SYSTEM, image_part, prompt],
            generation_config={"temperature": 0.1, "max_output_tokens": 4096},
        )
        return response.text or ""
    except Exception as e:
        logger.warning("Gemini Vision API xatoligi: %s", e)
        return ""


def _call_openrouter_vision(image_bytes: bytes, mime_type: str, prompt: str) -> str:
    """OpenRouter multimodal (vision) API orqali rasmni tahlil qilish."""
    api_key = getattr(settings, "OPENROUTER_API_KEY", "") or getattr(
        settings, "GROQ_API_KEY", ""
    )
    if not api_key:
        return ""

    import urllib.request

    base_url = (
        getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        if getattr(settings, "OPENROUTER_API_KEY", "")
        else getattr(settings, "GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    )

    model_name = (
        getattr(
            settings,
            "ESSAY_OCR_VISION_MODEL",
            "google/gemini-flash-1.5"
            if "openrouter" in base_url
            else "llama-3.2-11b-vision-preview",
        )
        or "google/gemini-flash-1.5"
    )

    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_uri = f"data:{mime_type};base64,{b64}"

    payload = {
        "model": model_name,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": PROMPT_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ],
    }

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"] or ""
    except Exception as e:
        logger.warning("OpenRouter Vision xatoligi: %s", e)
        return ""


def _call_text_llm(text_content: str, subject: str) -> str:
    """Matnli kontentni mavjud LLM client orqali structured testga aylantirish."""
    from apps.essays.services import (
        _chat_with_fallback,
        _get_llm_client,
        _is_mock_mode,
        _model_candidates,
    )

    if _is_mock_mode():
        return ""

    prompt = (
        f"Fan: {subject}\n"
        f"Quyidagi hujjat matnidan test savollari va variantlarini ajratib ol:\n\n"
        f"--- MATN BOSHI ---\n{text_content[:6000]}\n--- MATN YAKUNI ---\n\n"
        f"{PROMPT_JSON_INSTRUCTIONS}"
    )

    try:
        client = _get_llm_client(timeout=30.0)
        candidates = _model_candidates()
        resp, _ = _chat_with_fallback(
            client,
            candidates[0],
            candidates[1:],
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=3500,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning("Text LLM conversion xatoligi: %s", e)
        return ""


def _parse_raw_text_regex(raw_text: str, subject: str = "uzbek") -> dict[str, Any]:
    """
    LLM mavjud bo'lmaganda yoki mock rejimda matndan savollarni
    aniq regex andozalari asosida ajratib oluvchi aqlli deterministik parser.
    """
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if not lines:
        return _fallback_dummy_template(subject)

    questions: list[dict[str, Any]] = []
    current_q: dict[str, Any] | None = None
    reading_passage = ""

    # Matn ichida savol raqamini qidirish: "1.", "1)", "1 - savol", "№1"
    q_pattern = re.compile(r"^(?:№\s*|\b)?(\d+)[\.\)\-\s]\s*(.*)$")
    choice_pattern = re.compile(r"^([A-Ea-e])[\.\)\-\s]\s*(.*)$")

    for line in lines:
        qm = q_pattern.match(line)
        if qm and len(line) > 5 and not choice_pattern.match(line):
            q_num = int(qm.group(1))
            q_text = qm.group(2).strip() or line
            current_q = {
                "order": q_num,
                "text": q_text,
                "choices": [],
                "correct_answer": "A",
                "explanation": "Qoida asosida to'g'ri javob.",
                "question_type": "single_choice",
            }
            questions.append(current_q)
            continue

        cm = choice_pattern.match(line)
        if cm and current_q:
            c_code = cm.group(1).upper()
            c_text = cm.group(2).strip()
            current_q["choices"].append({"code": c_code, "text": c_text})
            continue

        # Agar savol ichida davom etayotgan matn bo'lsa
        if current_q and not current_q["choices"]:
            current_q["text"] += " " + line
        elif not current_q and len(line) > 40:
            reading_passage += (" " if reading_passage else "") + line

    # Variantlari to'liq bo'lmagan savollarga standart variantlar to'ldirish
    for idx, q in enumerate(questions, start=1):
        q["order"] = idx
        if not q["choices"]:
            q["choices"] = [
                {"code": "A", "text": "To'g'ri variant"},
                {"code": "B", "text": "Noto'g'ri variant"},
                {"code": "C", "text": "Chalg'ituvchi variant"},
                {"code": "D", "text": "Qo'shimcha variant"},
            ]
        elif len(q["choices"]) < 4:
            existing = {c["code"] for c in q["choices"]}
            for letter in ["A", "B", "C", "D"]:
                if letter not in existing:
                    q["choices"].append({"code": letter, "text": f"{letter} varianti"})
        q["choices"].sort(key=lambda x: x["code"])

    if not questions:
        return _fallback_dummy_template(subject)

    subject_label = (
        "Ona tili va adabiyot" if subject == "uzbek" else "Ingliz tili (CBT)"
    )
    return {
        "test_title": f"{subject_label} — AI bilan konvertatsiya qilingan test",
        "reading_passage": reading_passage.strip(),
        "questions": questions,
    }


def _fallback_dummy_template(subject: str = "uzbek") -> dict[str, Any]:
    """Hujjatda savollar aniqlanmaganda shablon sifatida tahrirga beriladigan namuna."""
    if subject == "english":
        return {
            "test_title": "IELTS / CEFR Reading Mock Test",
            "reading_passage": "Scientists have recently discovered that regular reading enhances cognitive flexibility and analytical processing in bilingual learners.",
            "questions": [
                {
                    "order": 1,
                    "text": "What is the primary benefit of regular reading mentioned in the text?",
                    "choices": [
                        {"code": "A", "text": "Enhanced cognitive flexibility"},
                        {"code": "B", "text": "Physical endurance improvement"},
                        {"code": "C", "text": "Faster typing speed"},
                        {"code": "D", "text": "Lower screen time"},
                    ],
                    "correct_answer": "A",
                    "explanation": "The text directly states that regular reading enhances cognitive flexibility.",
                    "question_type": "single_choice",
                },
                {
                    "order": 2,
                    "text": "According to the passage, which group of learners was specifically studied?",
                    "choices": [
                        {"code": "A", "text": "Bilingual learners"},
                        {"code": "B", "text": "Preschool children"},
                        {"code": "C", "text": "Professional athletes"},
                        {"code": "D", "text": "Musicians"},
                    ],
                    "correct_answer": "A",
                    "explanation": "Bilingual learners are explicitly identified as the subject of the study.",
                    "question_type": "single_choice",
                },
            ],
        }

    return {
        "test_title": "Ona tili va adabiyot — Milliy sertifikat diagnostika testi",
        "reading_passage": "Alisher Navoiy o'zbek adabiy tilining asoschisi bo'lib, uning 'Xamsa' asari turkiy tilda yaratilgan ilk beshlik hisoblanadi.",
        "questions": [
            {
                "order": 1,
                "text": "Quyidagi asarlardan qaysi biri Alisher Navoiy qalamiga mansub 'Xamsa' dostonlari tarkibiga kirmaydi?",
                "choices": [
                    {"code": "A", "text": "Hayrat ul-abror"},
                    {"code": "B", "text": "Farhod va Shirin"},
                    {"code": "C", "text": "Layli va Majnun"},
                    {"code": "D", "text": "Zafarnoma"},
                ],
                "correct_answer": "D",
                "explanation": "'Zafarnoma' Sharafiddin Ali Yazdiy tomonidan yozilgan tarixiy asardir, Navoiy 'Xamsa'siga kirmaydi.",
                "question_type": "single_choice",
            },
            {
                "order": 2,
                "text": "Turkiy tilda yaratilgan ilk 'Xamsa' qaysi mutafakkir tomonidan yozilgan?",
                "choices": [
                    {"code": "A", "text": "Alisher Navoiy"},
                    {"code": "B", "text": "Nizomiy Ganjaviy"},
                    {"code": "C", "text": "Xusrav Dehlaviy"},
                    {"code": "D", "text": "Abdurahmon Jomiy"},
                ],
                "correct_answer": "A",
                "explanation": "Turkiy tilda ilk bor butun 'Xamsa'ni Alisher Navoiy yaratgan (1483-1485 yillar).",
                "question_type": "single_choice",
            },
        ],
    }


def _clean_json_response(raw_resp: str) -> dict[str, Any] | None:
    """LLM javobidan JSON blokini xavfsiz ajratib olish va tozalash."""
    if not raw_resp:
        return None

    cleaned = raw_resp.strip()
    # Markdown ```json ``` o'rab turgan bo'lsa tozalash
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()

    try:
        data = json.loads(cleaned)
        if (
            isinstance(data, dict)
            and "questions" in data
            and isinstance(data["questions"], list)
        ):
            return data
    except Exception as e:
        logger.warning("JSON parsing xatoligi: %s (Raw: %s)", e, raw_resp[:200])

    return None


def convert_document_to_test_data(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    subject: str = "uzbek",
) -> dict[str, Any]:
    """
    Asosiy kirish funksiyasi:
    Yuklangan fayl (PDF yoki rasm)ni tahlil qilib, interaktiv test JSON ma'lumotlarini qaytaradi.
    """
    is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")
    is_image = content_type.startswith("image/") or filename.lower().endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".heic")
    )

    norm_subject = subject if subject in ("uzbek", "english") else "uzbek"
    subject_label = (
        "Ona tili va adabiyot (Milliy sertifikat)"
        if norm_subject == "uzbek"
        else "Ingliz tili (IELTS / CEFR)"
    )

    parsed_result: dict[str, Any] | None = None

    # 1. Agar PDF bo'lsa, avval matnli qatlamni tekshiramiz
    if is_pdf:
        pdf_text = _extract_text_from_pdf(file_bytes)
        if len(pdf_text) >= 60:
            # Matnli PDF: LLM ga to'g'ridan-to'g'ri yuboramiz
            llm_output = _call_text_llm(pdf_text, subject_label)
            parsed_result = _clean_json_response(llm_output)
            if not parsed_result:
                # LLM ishlamasa, regex parser bilan ajratib olamiz
                parsed_result = _parse_raw_text_regex(pdf_text, norm_subject)

    # 2. Agar rasm bo'lsa yoki PDF da matn topilmagan bo'lsa (skanerlangan)
    if not parsed_result and is_image:
        mime = content_type if content_type.startswith("image/") else "image/jpeg"
        prompt = (
            f"Fan yo'nalishi: {subject_label}.\n"
            f"Ushbu test fotosuratidagi barcha savollarni to'liq ajratib ol.\n"
            f"{PROMPT_JSON_INSTRUCTIONS}"
        )

        # Gemini Vision
        gemini_out = _call_gemini_vision(file_bytes, mime, prompt)
        parsed_result = _clean_json_response(gemini_out)

        # OpenRouter Vision fallback
        if not parsed_result:
            or_out = _call_openrouter_vision(file_bytes, mime, prompt)
            parsed_result = _clean_json_response(or_out)

    # 3. Agar hech qanday LLM yoki Vision muvaffaqiyatli bo'lmasa, deterministik xavfsiz shablon
    if not parsed_result:
        parsed_result = _fallback_dummy_template(norm_subject)

    # Natijani standartlashtirish
    questions = parsed_result.get("questions") or []
    for idx, q in enumerate(questions, start=1):
        q["order"] = idx
        if "correct_answer" not in q or not q["correct_answer"]:
            q["correct_answer"] = "A"
        if "explanation" not in q or not q["explanation"]:
            q["explanation"] = "Qoida asosida to'g'ri javob."
        if "choices" not in q or not q["choices"]:
            q["choices"] = [
                {"code": "A", "text": "Variant A"},
                {"code": "B", "text": "Variant B"},
                {"code": "C", "text": "Variant C"},
                {"code": "D", "text": "Variant D"},
            ]

    return {
        "test_title": parsed_result.get("test_title") or f"{subject_label} — AI Test",
        "reading_passage": parsed_result.get("reading_passage", "").strip(),
        "subject": norm_subject,
        "questions_count": len(questions),
        "questions": questions,
    }


@transaction.atomic
def save_converted_test(
    teacher,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Ustoz tomonidan tahrirlangan va tasdiqlangan savollarni bazada Test, Question va Choice
    obyektlari sifatida saqlaydi hamda unikal #MOCK-... kodi bilan nashr etadi.
    """
    title = str(payload.get("test_title") or "").strip() or "AI Mock Test"
    subject = str(payload.get("subject") or "uzbek").strip()
    time_limit = int(payload.get("time_limit_minutes") or 60)
    reading_passage_text = str(payload.get("reading_passage") or "").strip()
    questions_data = payload.get("questions") or []

    if not questions_data:
        raise ValueError("Saqlash uchun kamida 1 ta savol bo'lishi kerak.")

    mock_code = generate_unique_mock_code()
    course = _get_or_create_mock_course(teacher)

    test = Test.objects.create(
        course=course,
        subject=subject,
        title=title,
        description="Qog'oz / PDF hujjatdan AI Konvertor orqali yaratilgan rasmiy test.",
        time_limit_minutes=time_limit,
        status=Test.Status.PUBLISHED,
        is_active=True,
        mock_code=mock_code,
        shuffle_choices=False,
    )

    # Agar Reading Passage bo'lsa, yaratamiz
    passage_obj = None
    if reading_passage_text:
        passage_obj = ReadingPassage.objects.create(
            test=test,
            title=f"{title} — O'qish matni",
            content=reading_passage_text,
            order=1,
        )

    for idx, q_data in enumerate(questions_data, start=1):
        q_text = str(q_data.get("text") or "").strip() or f"{idx}-savol matni"
        correct_ans = str(q_data.get("correct_answer") or "A").strip().upper()
        explanation = str(q_data.get("explanation") or "").strip()

        question = Question.objects.create(
            test=test,
            reading_passage=passage_obj,
            text=q_text,
            question_type=Question.QuestionType.SINGLE_CHOICE,
            points=1,
            explanation=explanation,
            position=idx,
        )

        choices = q_data.get("choices") or []
        for c_idx, c in enumerate(choices, start=1):
            code = str(c.get("code") or chr(64 + c_idx)).strip().upper()
            c_text = str(c.get("text") or f"{code} varianti").strip()
            is_correct = code == correct_ans

            Choice.objects.create(
                question=question,
                text=c_text,
                is_correct=is_correct,
                position=c_idx,
            )

    return {
        "success": True,
        "test_id": test.id,
        "mock_code": mock_code,
        "title": test.title,
        "questions_count": len(questions_data),
        "message": f"Test muvaffaqiyatli saqlandi! Unikal ulanish kodi: {mock_code}",
    }
