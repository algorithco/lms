"""
OMR Answer Sheet Scanner Service (apps/tests/omr_service.py).

Two steps, so nothing is graded from a guess:

1. ``scan_sheet`` — validate the photo, read the marks with a vision model
   and return a per-question review (clear / multiple / blank / unread).
   No attempt is created and no XP is given.
2. ``confirm_sheet`` — the student checks and corrects the answers, then
   they are saved and graded through the same services as an online
   attempt (``StartAttemptService`` → ``SaveAnswerService`` →
   ``SubmitAttemptService``). CEFR tests therefore get exactly the same
   0–75 estimate as when taken online.

An unread or ambiguous mark is never turned into a default letter.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
import urllib.request
from typing import Any

from django.conf import settings
from django.utils.translation import gettext as _
from PIL import Image, ImageStat, UnidentifiedImageError

from apps.tests.numbering import NumberedQuestion, number_questions

logger = logging.getLogger(__name__)

CHOICE_LETTERS = "ABCDEFGHIJ"
ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}

CLEAR = "clear"
MULTIPLE = "multiple"
BLANK = "blank"
UNREAD = "unread"

TFNG_ALIASES = {
    "T": "TRUE",
    "F": "FALSE",
    "NG": "NOT GIVEN",
    "Y": "YES",
    "N": "NO",
}


class OmrError(Exception):
    """User-facing scan failure (bad image, not a sheet, unreadable)."""

    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


# ---------------------------------------------------------------------------
# Image validation
# ---------------------------------------------------------------------------


def validate_image(image_file) -> tuple[bytes, str]:
    """Reject anything that cannot be a photographed paper sheet.

    Checks: file size, real image format (not just the extension), minimum
    resolution, aspect ratio of a page, and that the picture is mostly light
    paper rather than a dark screen or a uniform blank frame.
    """
    max_bytes = settings.OMR_MAX_UPLOAD_BYTES
    if image_file.size and image_file.size > max_bytes:
        raise OmrError(
            "file_too_large",
            _("Rasm hajmi %(mb)s MB dan oshmasligi kerak.") % {"mb": max_bytes // (1024 * 1024)},
        )
    image_file.seek(0)
    data = image_file.read()
    image_file.seek(0)
    if len(data) > max_bytes:
        raise OmrError(
            "file_too_large",
            _("Rasm hajmi %(mb)s MB dan oshmasligi kerak.") % {"mb": max_bytes // (1024 * 1024)},
        )

    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise OmrError("bad_format", _("Faqat JPG, PNG yoki WEBP rasm yuklang."))
    if fmt not in ALLOWED_FORMATS:
        raise OmrError("bad_format", _("Faqat JPG, PNG yoki WEBP rasm yuklang."))

    w, h = img.size
    short, long_ = sorted((w, h))
    if short < settings.OMR_MIN_SHORT_SIDE:
        raise OmrError("not_a_sheet", _("Rasm juda kichik. Javoblar varaqasini yaqinroqdan aniq suratga oling."))
    if long_ / short > settings.OMR_MAX_ASPECT_RATIO:
        raise OmrError("not_a_sheet", _("Bu javoblar varaqasi emas, aniq suratga oling."))

    gray = img.convert("L")
    gray.thumbnail((400, 400))
    stat = ImageStat.Stat(gray)
    if stat.stddev[0] < 8:
        raise OmrError("not_a_sheet", _("Bu javoblar varaqasi emas, aniq suratga oling."))
    hist = gray.histogram()
    bright = sum(hist[150:]) / max(1, sum(hist))
    if bright < settings.OMR_MIN_PAPER_RATIO:
        raise OmrError("not_a_sheet", _("Bu javoblar varaqasi emas, aniq suratga oling."))

    return data, ALLOWED_FORMATS[fmt]


# ---------------------------------------------------------------------------
# Vision reading
# ---------------------------------------------------------------------------


def _prompt(keys: list[str]) -> str:
    return (
        "You are an Optical Mark Recognition reader for paper answer sheets.\n"
        "First decide whether the image is a photographed paper answer sheet with "
        "numbered rows of answer bubbles/boxes. Screenshots, video calls, slides, "
        "selfies, documents without answer rows are NOT answer sheets.\n"
        f"The expected answer rows are: {', '.join(keys)}.\n"
        "For every expected row report exactly what is marked:\n"
        '- a list with one letter, e.g. ["B"], when exactly one bubble is filled;\n'
        '- a list with several letters, e.g. ["A","C"], when more than one is filled;\n'
        "- an empty list [] when nothing is filled;\n"
        "- null when the row is missing, cut off, blurred or you are not sure.\n"
        "If a row holds handwritten words instead of bubbles, return them as one string in a list.\n"
        "Never guess. Never fill a default letter.\n"
        "Return only JSON, no markdown:\n"
        '{"is_answer_sheet": true, "test_code": "", "answers": {"<row>": ["A"]}}'
    )


def _call_vision(image_bytes: bytes, mime_type: str, prompt: str) -> str:
    api_key = getattr(settings, "OPENROUTER_API_KEY", "")
    if not api_key:
        raise OmrError(
            "scanner_unavailable",
            _("Skaner hozircha ishlamayapti. Javoblarni onlayn kiriting yoki keyinroq urinib ko'ring."),
            http_status=422,
        )
    base_url = getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    payload = {
        "model": settings.OMR_VISION_MODEL,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
                        },
                    },
                ],
            }
        ],
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.OMR_VISION_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"] or ""
    except Exception as exc:
        logger.warning("OMR vision request failed: %s", exc)
        raise OmrError(
            "scanner_unavailable",
            _("Skaner hozircha ishlamayapti. Javoblarni onlayn kiriting yoki keyinroq urinib ko'ring."),
            http_status=422,
        )


def _parse_json(text: str) -> dict[str, Any]:
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", clean, flags=re.DOTALL)
    try:
        data = json.loads(match.group(0) if match else clean)
    except (ValueError, AttributeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_marks(image_bytes: bytes, mime_type: str, keys: list[str]) -> dict[str, Any]:
    """Vision model → {"is_answer_sheet", "test_code", "answers"}; separate for mocking."""
    return _parse_json(_call_vision(image_bytes, mime_type, _prompt(keys)))


def _mark_status(raw: Any) -> tuple[str, str]:
    """Raw model value for one row → (status, value). Value only when clear."""
    if raw is None:
        return UNREAD, ""
    if isinstance(raw, str):
        raw = [raw] if raw.strip() else []
    if not isinstance(raw, list):
        return UNREAD, ""
    marks = [str(m).strip() for m in raw if str(m).strip() and str(m).strip() not in {"?", "-"}]
    if len(raw) and not marks:
        return UNREAD, ""
    if not marks:
        return BLANK, ""
    if len(marks) > 1:
        return MULTIPLE, ""
    return CLEAR, marks[0]


# ---------------------------------------------------------------------------
# Answer ↔ question mapping
# ---------------------------------------------------------------------------


def _answer_kind(q) -> str:
    if q.question_type in ("INLINE_GAP_FILL", "gap_fill", "SHORT_ANSWER", "text"):
        return "text"
    return "choice"


def _sorted_choices(q) -> list:
    return sorted(q.choices.all(), key=lambda c: (c.position, c.id))


def resolve_choice(q, value: str):
    """Sheet value ("B", "TRUE", "NG") → Choice of ``q``, or None."""
    v = (value or "").strip().upper().rstrip(".)")
    if not v:
        return None
    choices = _sorted_choices(q)
    # Exact option text first, then T/F/NG shorthand, then the letter index —
    # so "F" is option F in a matching task but FALSE in a T/F/NG task.
    for candidate in dict.fromkeys((v, TFNG_ALIASES.get(v, v))):
        for c in choices:
            text = (c.text or "").strip().upper()
            if text == candidate or re.match(rf"^{re.escape(candidate)}[\s.)\-:]", text):
                return c
    if len(v) == 1 and v in CHOICE_LETTERS:
        idx = CHOICE_LETTERS.index(v)
        if idx < len(choices):
            return choices[idx]
    return None


def correct_display(q) -> str:
    """Answer key as the student would write it on the sheet."""
    if _answer_kind(q) == "text":
        blank = q.gap_blanks.order_by("position", "id").first()
        if blank:
            return blank.answer_text
        return (q.correct_text or "").split("|")[0].strip()
    choices = _sorted_choices(q)
    for idx, c in enumerate(choices):
        if c.is_correct:
            return CHOICE_LETTERS[idx] if idx < len(CHOICE_LETTERS) else c.text
    return ""


def _review_item(nq: NumberedQuestion, status: str, value: str) -> dict[str, Any]:
    q = nq.question
    kind = _answer_kind(q)
    options: list[str] = []
    if kind == "choice":
        options = [CHOICE_LETTERS[i] for i in range(min(len(_sorted_choices(q)), len(CHOICE_LETTERS)))]
        if status == CLEAR and resolve_choice(q, value) is None:
            # A letter the question does not have — treat as unread, not as "A".
            status, value = UNREAD, ""
        elif status == CLEAR:
            value = CHOICE_LETTERS[_sorted_choices(q).index(resolve_choice(q, value))]
    return {
        "question_id": q.id,
        "key": nq.key,
        "number": nq.number,
        "section_code": nq.section_code,
        "kind": kind,
        "options": options,
        "status": status,
        "value": value,
    }


# ---------------------------------------------------------------------------
# Test lookup
# ---------------------------------------------------------------------------


def omr_tests_queryset():
    from apps.tests.models import Test

    return Test.objects.filter(is_active=True).exclude(status=Test.Status.ARCHIVED)


def resolve_test(test_id: int | None, mock_code: str | None, detected_code: str = ""):
    qs = omr_tests_queryset()
    if test_id:
        return qs.filter(pk=test_id).first()
    for code in (mock_code, detected_code):
        code = (code or "").strip()
        if code:
            test = qs.filter(mock_code__iexact=code).first()
            if test:
                return test
    return None


# ---------------------------------------------------------------------------
# Step 1: scan
# ---------------------------------------------------------------------------


def scan_sheet(image_file, test_id: int | None = None, mock_code: str | None = None) -> dict[str, Any]:
    image_bytes, mime = validate_image(image_file)

    test = resolve_test(test_id, mock_code)
    if test_id and not test:
        raise OmrError("test_not_found", _("Test topilmadi yoki faol emas."), http_status=404)
    if not test:
        raise OmrError("test_required", _("Iltimos, ro'yxatdan qaysi testga javob berganingizni tanlang."))

    numbered = number_questions(test)
    if not numbered:
        raise OmrError("no_objective_questions", _("Bu testda javoblar varaqasi bilan tekshiriladigan savollar yo'q."))

    extracted = read_marks(image_bytes, mime, [nq.key for nq in numbered])
    if extracted.get("is_answer_sheet") is not True:
        raise OmrError("not_a_sheet", _("Bu javoblar varaqasi emas, aniq suratga oling."))

    answers = extracted.get("answers") if isinstance(extracted.get("answers"), dict) else {}
    items = []
    for nq in numbered:
        status, value = _mark_status(answers.get(nq.key))
        items.append(_review_item(nq, status, value))

    unread = sum(1 for i in items if i["status"] == UNREAD)
    ratio = unread / len(items)
    if ratio > settings.OMR_MAX_UNREAD_RATIO:
        raise OmrError(
            "unreadable",
            _("Varaqdagi %(n)s ta savol o'qilmadi. Varaqni yorug' joyda, to'liq va aniq suratga oling.")
            % {"n": unread},
        )

    counts = {s: sum(1 for i in items if i["status"] == s) for s in (CLEAR, MULTIPLE, BLANK, UNREAD)}
    return {
        "ok": True,
        "test_id": test.id,
        "test_title": test.title,
        "exam_type": test.exam_type,
        "subject": test.subject,
        "detected_code": str(extracted.get("test_code") or ""),
        "total_questions": len(items),
        "counts": counts,
        "items": items,
    }


# ---------------------------------------------------------------------------
# Step 2: confirm → grade with the online pipeline
# ---------------------------------------------------------------------------


def confirm_sheet(test_id: int, answers: dict[str, Any], user) -> dict[str, Any]:
    """Save the student-confirmed answers as a normal attempt and grade it.

    ``answers`` maps question_id → value ("B", "NG", "library", or "" for
    blank). No XP is awarded for OMR results.
    """
    from apps.tests.models import TestAttempt
    from apps.tests.services import SaveAnswerService, StartAttemptService, SubmitAttemptService

    test = omr_tests_queryset().filter(pk=test_id).first()
    if not test:
        raise OmrError("test_not_found", _("Test topilmadi yoki faol emas."), http_status=404)

    if TestAttempt.objects.filter(test=test, student=user, status=TestAttempt.Status.IN_PROGRESS).exists():
        raise OmrError(
            "attempt_in_progress",
            _("Bu test bo'yicha davom etayotgan onlayn urinishingiz bor. Avval uni yakunlang."),
            http_status=409,
        )

    numbered = {nq.question.id: nq for nq in number_questions(test)}
    clean: dict[int, str] = {}
    for raw_id, raw_value in (answers or {}).items():
        try:
            qid = int(raw_id)
        except (TypeError, ValueError):
            continue
        if qid not in numbered:
            raise OmrError("bad_answers", _("Javoblar ro'yxati bu testga mos emas."))
        value = str(raw_value or "").strip()[:200]
        if not value:
            continue
        q = numbered[qid].question
        if _answer_kind(q) == "choice" and resolve_choice(q, value) is None:
            raise OmrError(
                "bad_answers",
                _("%(key)s-savol uchun javob noto'g'ri: %(value)s") % {"key": numbered[qid].key, "value": value},
            )
        clean[qid] = value

    try:
        attempt = StartAttemptService.execute(test_id=test.id, student=user)
    except ValueError as exc:
        raise OmrError("start_denied", str(exc), http_status=403)

    for qid, value in clean.items():
        q = numbered[qid].question
        if _answer_kind(q) == "choice":
            SaveAnswerService.execute(
                attempt_id=attempt.id, question_id=qid, student=user,
                choice_ids=[resolve_choice(q, value).id],
            )
        else:
            blank = q.gap_blanks.order_by("position").first()
            SaveAnswerService.execute(
                attempt_id=attempt.id, question_id=qid, student=user,
                text_answer=value,
                gap_answers={blank.position: value} if blank else None,
            )

    result = SubmitAttemptService.execute(attempt_id=attempt.id, student=user)
    attempt.refresh_from_db()
    from apps.results.models import Result

    result_row = Result.objects.filter(attempt=attempt).only("id").first()
    return {
        "ok": True,
        "attempt_id": attempt.id,
        "result_id": result_row.id if result_row else None,
        "is_preview": attempt.is_preview,
        "exam_type": test.exam_type,
        "percentage": float(getattr(result, "percentage", 0) or 0),
        "xp_earned": 0,
    }
