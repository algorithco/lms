"""
Automated Score Converter for English Exams (IELTS Academic/General & CEFR Multi-level).

Implements official conversion scales:
1. Raw Score (0–40) -> IELTS Band (1.0–9.0)
2. Raw Score -> CEFR Multi-level (BMB Davlat Imtihoni 70/75 ball shkalasi -> A2, B1, B2, C1)
3. Component aggregation & Official IELTS Half-Band Rounding Rules
4. Digital Certificate / Result Card Payload Generator
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any


def raw_to_ielts_band(
    raw_score: int | float | Decimal, total_questions: int = 40
) -> Decimal:
    """
    Convert raw score to official IELTS Band (1.0 - 9.0).

    Official IELTS 40-question scale:
        39–40: Band 9.0
        37–38: Band 8.5
        35–36: Band 8.0
        32–34: Band 7.5
        30–31: Band 7.0
        26–29: Band 6.5
        23–25: Band 6.0
        19–22: Band 5.5
        15–18: Band 5.0
        13–14: Band 4.5
        10–12: Band 4.0
        0–9:   Band 3.5 and below
    """
    raw = float(raw_score)
    if total_questions > 0 and total_questions != 40:
        raw = round((raw / total_questions) * 40.0)

    raw_int = int(round(raw))

    if raw_int >= 39:
        return Decimal("9.0")
    if raw_int >= 37:
        return Decimal("8.5")
    if raw_int >= 35:
        return Decimal("8.0")
    if raw_int >= 32:
        return Decimal("7.5")
    if raw_int >= 30:
        return Decimal("7.0")
    if raw_int >= 26:
        return Decimal("6.5")
    if raw_int >= 23:
        return Decimal("6.0")
    if raw_int >= 19:
        return Decimal("5.5")
    if raw_int >= 15:
        return Decimal("5.0")
    if raw_int >= 13:
        return Decimal("4.5")
    if raw_int >= 10:
        return Decimal("4.0")
    if raw_int >= 7:
        return Decimal("3.5")
    if raw_int >= 5:
        return Decimal("3.0")
    if raw_int >= 3:
        return Decimal("2.5")
    if raw_int >= 1:
        return Decimal("2.0")
    return Decimal("1.0")


def raw_to_cefr_multilevel(
    raw_score: int | float | Decimal,
    max_score: int | float | Decimal = 75,
) -> tuple[str, Decimal]:
    """
    Convert raw score to CEFR Multi-level (BMB Davlat Imtihoni).

    Scale:
        65–75 ball ekvivalenti: C1 darajasi
        51–64 ball: B2 darajasi
        36–50 ball: B1 darajasi
        35 va undan past: Sertifikat berilmaydi (A2)

    Returns:
        tuple[str, Decimal]: (CEFR level name, standardized score)
    """
    score = float(raw_score)
    max_s = float(max_score) if max_score > 0 else 75.0

    # Scale to 75-point standard if different max
    if max_s != 75.0:
        standardized = round((score / max_s) * 75.0, 1)
    else:
        standardized = round(score, 1)

    std_dec = Decimal(str(standardized))

    if standardized >= 65.0:
        return "C1", std_dec
    if standardized >= 51.0:
        return "B2", std_dec
    if standardized >= 36.0:
        return "B1", std_dec
    return "A2", std_dec


def ielts_band_to_cefr(band: Decimal | float | int) -> str:
    """Map IELTS band score to CEFR level equivalent."""
    b = float(band)
    if b >= 8.5:
        return "C2"
    if b >= 7.0:
        return "C1"
    if b >= 5.5:
        return "B2"
    if b >= 4.0:
        return "B1"
    return "A2"


def calculate_overall_ielts_band(
    listening: Decimal | float | int,
    reading: Decimal | float | int,
    writing: Decimal | float | int,
    speaking: Decimal | float | int,
) -> Decimal:
    """
    Calculate overall IELTS Band score with official Cambridge half-band rounding rule.

    Cambridge Rounding Rule:
        - Compute arithmetic mean: average = (L + R + W + S) / 4
        - If fractional part is:
            < 0.25      -> rounds down to integer (e.g. 6.125 -> 6.0)
            >= 0.25 and < 0.75 -> rounds to half band (e.g. 6.25 -> 6.5, 6.625 -> 6.5)
            >= 0.75     -> rounds up to next integer (e.g. 6.75 -> 7.0)
    """
    scores = [float(listening), float(reading), float(writing), float(speaking)]
    avg = sum(scores) / 4.0

    int_part = math.floor(avg)
    fraction = avg - int_part

    if fraction < 0.25:
        rounded = float(int_part)
    elif fraction < 0.75:
        rounded = float(int_part) + 0.5
    else:
        rounded = float(int_part) + 1.0

    # Keep in bounds [1.0, 9.0]
    rounded = max(1.0, min(9.0, rounded))
    return Decimal(f"{rounded:.1f}")


def calculate_overall_cefr_level(
    section_scores: dict[str, int | float | Decimal],
    total_sections: int = 4,
) -> tuple[str, Decimal]:
    """
    Calculate aggregate CEFR level from section scores (Listening, Reading, Writing, Speaking).
    Scores are expected on a 75-point equivalent per section or total average.
    """
    if not section_scores:
        return "A2", Decimal("0")

    values = [float(v) for v in section_scores.values()]
    avg_score = sum(values) / max(len(values), 1)
    level, score_dec = raw_to_cefr_multilevel(avg_score, max_score=75)
    return level, score_dec


def convert_test_score_to_english_band(result_or_attempt: Any) -> dict[str, Any]:
    """
    Examines a TestAttempt or Result instance, parses section scores or overall points,
    and returns comprehensive IELTS and CEFR conversions.
    """
    # Extract total questions and correct answers
    total_q = getattr(result_or_attempt, "total_questions", 40) or 40
    correct_q = getattr(result_or_attempt, "correct_answers", None)
    if correct_q is None:
        correct_q = getattr(result_or_attempt, "score", 0) or 0

    raw_score = int(round(float(correct_q)))

    ielts_band = raw_to_ielts_band(raw_score, total_questions=total_q)
    cefr_level, std_score = raw_to_cefr_multilevel(raw_score, max_score=total_q)

    # Check for section scores if available
    sections_data = {}
    sec_scores_rel = getattr(result_or_attempt, "section_scores", None)
    if sec_scores_rel and hasattr(sec_scores_rel, "all"):
        for ss in sec_scores_rel.all():
            code = (ss.section_code or "").lower()
            earned = float(ss.earned)
            maximum = float(ss.maximum) or 40.0
            sec_band = raw_to_ielts_band(earned, total_questions=int(maximum))
            sec_cefr, _ = raw_to_cefr_multilevel(earned, max_score=maximum)
            sections_data[code] = {
                "name": ss.section_name or code.capitalize(),
                "earned": earned,
                "maximum": maximum,
                "band": float(sec_band),
                "cefr": sec_cefr,
            }

    # If 4 skills present, calculate Cambridge overall band
    if all(k in sections_data for k in ["listening", "reading", "writing", "speaking"]):
        overall_band = calculate_overall_ielts_band(
            sections_data["listening"]["band"],
            sections_data["reading"]["band"],
            sections_data["writing"]["band"],
            sections_data["speaking"]["band"],
        )
        overall_cefr = ielts_band_to_cefr(overall_band)
    else:
        overall_band = ielts_band
        overall_cefr = cefr_level

    return {
        "raw_score": raw_score,
        "total_questions": total_q,
        "percentage": float(getattr(result_or_attempt, "percentage", 0.0)),
        "ielts_band": float(overall_band),
        "cefr_level": overall_cefr,
        "standardized_score": float(std_score),
        "sections": sections_data,
        "has_certificate": overall_cefr in ["B1", "B2", "C1", "C2"],
    }


def generate_digital_certificate_payload(
    student_name: str,
    exam_title: str,
    exam_type: str,
    score_info: dict[str, Any],
    completion_date: str | None = None,
    certificate_number: str | None = None,
) -> dict[str, Any]:
    """
    Generates structured JSON payload for A4 Digital Certificate and Result Card.
    """
    from django.utils import timezone

    date_str = completion_date or timezone.now().strftime("%d.%m.%Y")
    cert_no = (
        certificate_number or f"GR-EN-{int(timezone.now().timestamp()) % 1000000:06d}"
    )

    overall_band = score_info.get("ielts_band", 6.5)
    overall_cefr = score_info.get("cefr_level", "B2")

    return {
        "certificate_number": cert_no,
        "title": "OFFICIAL ENGLISH PROFICIENCY CERTIFICATE",
        "subtitle": "GRAND EDUCATION ACADEMIC ASSESSMENT HUB",
        "candidate_name": student_name,
        "exam_title": exam_title,
        "exam_type": exam_type,
        "issue_date": date_str,
        "overall_band": overall_band,
        "overall_cefr": overall_cefr,
        "grade_description": (
            "Independent User (Competent)"
            if overall_band < 7.0
            else "Proficient User (Advanced)"
        ),
        "sections": score_info.get("sections", {}),
        "qr_verification_url": f"https://grandec.uz/verify-certificate/?code={cert_no}",
        "issuer": "GRAND EDUCATION Assessment Board",
        "is_valid": score_info.get("has_certificate", True),
    }
