"""
Grand Education LMS — Automated PDF Vedomost & Exam Report Generator (ReportLab).

Provides:
1. generate_student_vedomost_pdf(attempt_id: int) -> str:
   Generates a professional individual student scorecard / vedomost PDF.
2. generate_group_vedomost_pdf(group_id: int, test_id: int | None = None) -> str:
   Generates a comprehensive group exam vedomost / leaderboard PDF.
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal
from io import BytesIO
from typing import Any

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

try:
    import qrcode

    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Colors & Styles
# ---------------------------------------------------------------------------
class VedomostColors:
    PRIMARY = colors.HexColor("#1e3a8a")       # Blue 900
    SECONDARY = colors.HexColor("#2563eb")     # Blue 600
    ACCENT = colors.HexColor("#0284c7")        # Sky 600
    DARK_TEXT = colors.HexColor("#0f172a")     # Slate 900
    MUTED_TEXT = colors.HexColor("#475569")    # Slate 600
    LIGHT_BG = colors.HexColor("#f8fafc")      # Slate 50
    HEADER_BG = colors.HexColor("#e2e8f0")     # Slate 200
    BORDER = colors.HexColor("#cbd5e1")        # Slate 300
    SUCCESS = colors.HexColor("#16a34a")       # Green 600
    SUCCESS_BG = colors.HexColor("#dcfce7")    # Green 100
    DANGER = colors.HexColor("#dc2626")        # Red 600
    DANGER_BG = colors.HexColor("#fee2e2")     # Red 100
    GOLD = colors.HexColor("#d97706")          # Amber 600


def _get_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle(
            "VedomostTitle",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=VedomostColors.PRIMARY,
            alignment=1,  # Center
        ),
        "subtitle": ParagraphStyle(
            "VedomostSubtitle",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=VedomostColors.MUTED_TEXT,
            alignment=1,  # Center
        ),
        "section_heading": ParagraphStyle(
            "VedomostSectionHeading",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=VedomostColors.PRIMARY,
            spaceAfter=4,
        ),
        "cell_bold": ParagraphStyle(
            "VedomostCellBold",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=VedomostColors.DARK_TEXT,
        ),
        "cell": ParagraphStyle(
            "VedomostCell",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=VedomostColors.DARK_TEXT,
        ),
        "cell_center": ParagraphStyle(
            "VedomostCellCenter",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=VedomostColors.DARK_TEXT,
            alignment=1,
        ),
        "cell_bold_center": ParagraphStyle(
            "VedomostCellBoldCenter",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=VedomostColors.DARK_TEXT,
            alignment=1,
        ),
        "metric_value": ParagraphStyle(
            "VedomostMetricValue",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=VedomostColors.PRIMARY,
            alignment=1,
        ),
        "metric_label": ParagraphStyle(
            "VedomostMetricLabel",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=VedomostColors.MUTED_TEXT,
            alignment=1,
        ),
        "footer_text": ParagraphStyle(
            "VedomostFooterText",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=VedomostColors.MUTED_TEXT,
        ),
    }
    return styles


def _generate_qr_code(url: str, size: float = 2.4 * cm) -> Image | None:
    if not HAS_QRCODE:
        return None
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1e3a8a", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Image(buf, width=size, height=size)
    except Exception as exc:
        logger.warning("Vedomost QR code generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# 1. Single Student Scorecard / Vedomost PDF
# ---------------------------------------------------------------------------
def generate_student_vedomost_pdf(attempt_id: int) -> str:
    """
    Generates an official A4 portrait student scorecard PDF.
    Returns the absolute path to the generated PDF.
    """
    from apps.tests.models import TestAttempt
    from apps.results.models import Result

    attempt = (
        TestAttempt.objects.select_related("test", "student", "test__assigned_group", "graded_by")
        .prefetch_related("answers", "answers__question", "answers__question__section")
        .get(id=attempt_id)
    )

    test = attempt.test
    student = attempt.student

    # Group lookup
    group = test.assigned_group
    if not group:
        group = student.student_groups.first()
    group_name = group.name if group else "Mustaqil ta'lim (Individual)"

    # Result lookup
    result = Result.objects.filter(attempt=attempt).first()

    # Create target directory
    vedomost_dir = os.path.join(settings.MEDIA_ROOT, "vedomost")
    os.makedirs(vedomost_dir, exist_ok=True)
    filename = f"vedomost_student_{attempt.id}_{int(timezone.now().timestamp())}.pdf"
    file_path = os.path.join(vedomost_dir, filename)

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = _get_styles()
    story: list[Any] = []

    # -- Header ---------------------------------------------------------------
    story.append(Paragraph("GRAND EDUCATION LMS", styles["title"]))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("RASMIY IMTIHON VEDOMOSTI / OFFICIAL EXAMINATION SCORECARD", styles["subtitle"]))
    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=VedomostColors.PRIMARY, spaceAfter=8))

    # -- Student & Exam Meta Table --------------------------------------------
    date_str = (
        attempt.completed_at.strftime("%d.%m.%Y %H:%M")
        if attempt.completed_at
        else (attempt.started_at.strftime("%d.%m.%Y %H:%M") if attempt.started_at else "-")
    )
    time_taken_mins = 0
    if attempt.completed_at and attempt.started_at:
        time_taken_mins = max(1, int((attempt.completed_at - attempt.started_at).total_seconds() // 60))

    student_name = student.get_full_name() or student.email
    teacher_name = attempt.graded_by.get_full_name() if attempt.graded_by else (
        group.teacher.get_full_name() if (group and group.teacher) else "Avtomatik tizim"
    )

    branch = getattr(group, "branch", None) or getattr(student, "branch", None)
    branch_title = branch.name if branch else "Grand Education Bosh Filiali"
    if branch and getattr(branch, "branch_code", None):
        branch_title += f" ({branch.branch_code})"

    subject_slug = getattr(test, "subject", "uzbek")
    subj_names = {
        "biology": "Biologiya (Milliy sertifikat)",
        "chemistry": "Kimyo (Milliy sertifikat)",
        "law": "Huquqshunoslik (Yurisprudensiya)",
        "uzbek": "Ona tili va Adabiyot",
        "english": "Ingliz tili (CEFR / IELTS)",
    }
    subj_title = subj_names.get(subject_slug, str(subject_slug).title())

    meta_data = [
        [
            Paragraph("<b>O'quvchi F.I.Sh:</b>", styles["cell"]),
            Paragraph(student_name, styles["cell_bold"]),
            Paragraph("<b>Imtihon / Test:</b>", styles["cell"]),
            Paragraph(test.title, styles["cell_bold"]),
        ],
        [
            Paragraph("<b>Filial / Kursxona:</b>", styles["cell"]),
            Paragraph(branch_title, styles["cell"]),
            Paragraph("<b>Fan yo'nalishi:</b>", styles["cell"]),
            Paragraph(subj_title, styles["cell_bold"]),
        ],
        [
            Paragraph("<b>Guruh:</b>", styles["cell"]),
            Paragraph(group_name, styles["cell"]),
            Paragraph("<b>Topshirilgan sana:</b>", styles["cell"]),
            Paragraph(date_str, styles["cell"]),
        ],
        [
            Paragraph("<b>ID / Raqam:</b>", styles["cell"]),
            Paragraph(f"ATT-{attempt.id:06d}", styles["cell"]),
            Paragraph("<b>Sarflangan vaqt:</b>", styles["cell"]),
            Paragraph(f"{time_taken_mins} daqiqa", styles["cell"]),
        ],
        [
            Paragraph("<b>Tekshiruvchi:</b>", styles["cell"]),
            Paragraph(teacher_name, styles["cell"]),
            Paragraph("<b>Status:</b>", styles["cell"]),
            Paragraph(attempt.get_status_display(), styles["cell"]),
        ],
    ]

    meta_table = Table(meta_data, colWidths=[35 * mm, 55 * mm, 35 * mm, 55 * mm])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), VedomostColors.LIGHT_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 5 * mm))

    # -- Key Metrics Cards ----------------------------------------------------
    max_score = result.max_score if result else (sum(q.points for q in test.questions.all()) or 100)
    score_display = f"{attempt.score:g} / {max_score:g}"
    pct_display = f"{attempt.percentage:.1f}%"
    status_text = "O'TDI (PASSED)" if attempt.is_passed else "O'TMADI (FAILED)"
    status_color = VedomostColors.SUCCESS if attempt.is_passed else VedomostColors.DANGER

    band_or_level = attempt.cefr_level or (f"Band {attempt.band_score}" if attempt.band_score else attempt.rasch_grade or "-")

    metrics_data = [
        [
            Paragraph(score_display, styles["metric_value"]),
            Paragraph(pct_display, styles["metric_value"]),
            Paragraph(f"<font color='{status_color.hexval()}'>{status_text}</font>", styles["metric_value"]),
            Paragraph(str(band_or_level), styles["metric_value"]),
        ],
        [
            Paragraph("UMUMIY BALL", styles["metric_label"]),
            Paragraph("FOIZ KO'RSATKICHI", styles["metric_label"]),
            Paragraph("NATIJA", styles["metric_label"]),
            Paragraph("CEFR / BAND DARAJA", styles["metric_label"]),
        ],
    ]

    metrics_table = Table(metrics_data, colWidths=[45 * mm, 45 * mm, 45 * mm, 45 * mm])
    metrics_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 1, VedomostColors.SECONDARY),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(metrics_table)
    story.append(Spacer(1, 6 * mm))

    # -- Section Breakdown Table ----------------------------------------------
    story.append(Paragraph("BO'LIMLAR BO'YICHA BALLAR TAQSIMOTI (SECTION BREAKDOWN)", styles["section_heading"]))

    section_table_data = [
        [
            Paragraph("<b>Bo'lim (Section)</b>", styles["cell_bold"]),
            Paragraph("<b>To'plangan ball</b>", styles["cell_bold_center"]),
            Paragraph("<b>Maksimal ball</b>", styles["cell_bold_center"]),
            Paragraph("<b>Foiz (%)</b>", styles["cell_bold_center"]),
            Paragraph("<b>Holat</b>", styles["cell_bold_center"]),
        ]
    ]

    # Check if section_scores exists in attempt or ResultSectionScore
    sec_scores = attempt.section_scores or {}
    if not sec_scores and result:
        for rss in result.section_scores.all():
            sec_scores[rss.section_code or rss.section_name] = {
                "earned": float(rss.earned),
                "maximum": float(rss.maximum),
                "name": rss.section_name or rss.section_code,
            }

    if sec_scores:
        for code, details in sec_scores.items():
            if isinstance(details, dict):
                earned = float(details.get("earned", 0))
                maximum = float(details.get("maximum", 0))
                name = details.get("name", code)
            else:
                earned = float(details)
                maximum = float(details)
                name = code

            pct = round((earned / maximum * 100.0), 1) if maximum > 0 else 0.0
            sec_status = "A'lo" if pct >= 85 else ("Yaxshi" if pct >= 60 else "Qoniqarsiz")

            section_table_data.append([
                Paragraph(str(name), styles["cell"]),
                Paragraph(f"{earned:g}", styles["cell_center"]),
                Paragraph(f"{maximum:g}", styles["cell_center"]),
                Paragraph(f"{pct}%", styles["cell_center"]),
                Paragraph(sec_status, styles["cell_center"]),
            ])
    else:
        # Fallback to single row summary
        section_table_data.append([
            Paragraph("Asosiy test (Umumiy)", styles["cell"]),
            Paragraph(f"{attempt.score:g}", styles["cell_center"]),
            Paragraph(f"{max_score:g}", styles["cell_center"]),
            Paragraph(f"{attempt.percentage:.1f}%", styles["cell_center"]),
            Paragraph("Bajarildi" if attempt.is_passed else "Qoniqarsiz", styles["cell_center"]),
        ])

    sec_table = Table(section_table_data, colWidths=[60 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm])
    sec_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VedomostColors.HEADER_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(sec_table)
    story.append(Spacer(1, 6 * mm))

    # -- AI & Teacher Diagnostics / Comments ----------------------------------
    story.append(Paragraph("USTOZ VA INTELLEKTUAL DIAGNOSTIKA IZOHI", styles["section_heading"]))

    teacher_note = attempt.teacher_comment.strip() if attempt.teacher_comment else ""
    if not teacher_note:
        if attempt.is_passed:
            teacher_note = "Imtihon muvaffaqiyatli topshirildi. Natijalar me'yor darajasida qayd etildi."
        else:
            teacher_note = "Imtihondan o'tish uchun yetarli ball to'planmadi. Xatolar ustida mustaqil ishlash tavsiya etiladi."

    comment_content = [
        Paragraph(f"<b>Ustoz xulosasi:</b> {teacher_note}", styles["cell"]),
    ]
    if attempt.teacher_overridden:
        comment_content.append(
            Paragraph("<i>* Eslatma: Ushbu urinish ballari o'qituvchi tomonidan ekspert tekshiruvi asosida tasdiqlangan va qayta hisoblangan.</i>", styles["footer_text"])
        )

    comment_table = Table([[comment_content]], colWidths=[180 * mm])
    comment_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(comment_table)
    story.append(Spacer(1, 8 * mm))

    # -- Verification & Signature Area ----------------------------------------
    base_url = getattr(settings, "SITE_URL", "https://grandec.uz")
    verify_url = f"{base_url}/tests/attempts/{attempt.id}/details/"
    qr_img = _generate_qr_code(verify_url, size=2.2 * cm)

    sig_col1 = [
        Paragraph("<b>Grand Education LMS — Imtihonlar Nazorati</b>", styles["cell"]),
        Spacer(1, 2 * mm),
        Paragraph(f"Hujjat sanasi: {timezone.now().strftime('%d.%m.%Y %H:%M')}", styles["footer_text"]),
        Paragraph(f"Tekshirish kodi: ATT-{attempt.id:06d}-V{attempt.percentage:.0f}", styles["footer_text"]),
        Spacer(1, 4 * mm),
        Paragraph("Ustoz imzosi: __________________________", styles["cell"]),
    ]

    sig_cells = [
        [
            sig_col1,
            qr_img if qr_img else Paragraph("", styles["cell"]),
        ]
    ]
    sig_table = Table(sig_cells, colWidths=[140 * mm, 40 * mm])
    sig_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ])
    )
    story.append(KeepTogether(sig_table))

    doc.build(story)
    logger.info("Student vedomost PDF generated: %s (attempt_id=%s)", file_path, attempt_id)
    return file_path


# ---------------------------------------------------------------------------
# 2. Group Exam Vedomost Table PDF
# ---------------------------------------------------------------------------
def generate_group_vedomost_pdf(group_id: int, test_id: int | None = None) -> str:
    """
    Generates a full group vedomost / leaderboard PDF in A4 landscape format.
    Returns the absolute path to the generated PDF.
    """
    from apps.courses.models import StudentGroup
    from apps.tests.models import Test, TestAttempt

    group = StudentGroup.objects.prefetch_related("students", "teacher").get(id=group_id)

    # Determine test
    if test_id:
        test = Test.objects.get(id=test_id)
    else:
        test = Test.objects.filter(assigned_group=group).order_by("-id").first()
        if not test:
            # Fallback to recent test taken by group students
            recent_attempt = (
                TestAttempt.objects.filter(student__in=group.students.all())
                .order_by("-started_at")
                .first()
            )
            test = recent_attempt.test if recent_attempt else None

    vedomost_dir = os.path.join(settings.MEDIA_ROOT, "vedomost")
    os.makedirs(vedomost_dir, exist_ok=True)
    filename = f"vedomost_group_{group.id}_{int(timezone.now().timestamp())}.pdf"
    file_path = os.path.join(vedomost_dir, filename)

    doc = SimpleDocTemplate(
        file_path,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = _get_styles()
    story: list[Any] = []

    # -- Header ---------------------------------------------------------------
    test_title = test.title if test else "Guruh Sinov Imtihoni"
    story.append(Paragraph("GRAND EDUCATION LMS", styles["title"]))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"GURUH IMTIHON VEDOMOSTI — {group.name.upper()}", styles["subtitle"]))
    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=VedomostColors.PRIMARY, spaceAfter=6))

    # -- Meta Info ------------------------------------------------------------
    teacher_name = group.teacher.get_full_name() if group.teacher else "Tayinlanmagan"
    now_str = timezone.now().strftime("%d.%m.%Y %H:%M")

    group_students = list(group.students.all().order_by("first_name", "last_name", "email"))
    total_students = len(group_students)

    attempts_qs = TestAttempt.objects.filter(
        student__in=group_students,
        is_preview=False,
        status__in=[TestAttempt.Status.COMPLETED, TestAttempt.Status.TIMEOUT],
    )
    if test:
        attempts_qs = attempts_qs.filter(test=test)

    # Pick latest attempt per student
    student_attempt_map: dict[int, Any] = {}
    for att in attempts_qs.order_by("started_at"):
        student_attempt_map[att.student_id] = att

    participated_count = len(student_attempt_map)
    avg_pct = (
        sum(att.percentage for att in student_attempt_map.values()) / participated_count
        if participated_count > 0
        else Decimal("0.00")
    )
    passed_count = sum(1 for att in student_attempt_map.values() if att.is_passed)
    pass_rate = round((passed_count / participated_count * 100), 1) if participated_count > 0 else 0.0

    branch = getattr(group, "branch", None)
    branch_title = branch.name if branch else "Grand Education Bosh Filiali"
    if branch and getattr(branch, "branch_code", None):
        branch_title += f" ({branch.branch_code})"

    subj_slug = getattr(group, "subject", None) or (getattr(test, "subject", None) if test else "uzbek")
    subj_names = {
        "biology": "Biologiya (Milliy sertifikat)",
        "chemistry": "Kimyo (Milliy sertifikat)",
        "law": "Huquqshunoslik",
        "uzbek": "Ona tili va Adabiyot",
        "english": "Ingliz tili",
    }
    subj_title = subj_names.get(subj_slug, str(subj_slug).title())

    meta_cols = [
        [
            Paragraph("<b>Filial:</b>", styles["cell"]),
            Paragraph(branch_title, styles["cell_bold"]),
            Paragraph("<b>Guruh:</b>", styles["cell"]),
            Paragraph(group.name, styles["cell_bold"]),
            Paragraph("<b>Fan:</b>", styles["cell"]),
            Paragraph(subj_title, styles["cell_bold"]),
        ],
        [
            Paragraph("<b>Ustoz:</b>", styles["cell"]),
            Paragraph(teacher_name, styles["cell"]),
            Paragraph("<b>Imtihon:</b>", styles["cell"]),
            Paragraph(test_title, styles["cell"]),
            Paragraph("<b>O'rtacha ko'rsatkich:</b>", styles["cell"]),
            Paragraph(f"{avg_pct:.1f}% ({participated_count}/{total_students} nafar)", styles["cell_bold"]),
        ],
    ]
    meta_table = Table(meta_cols, colWidths=[25 * mm, 60 * mm, 25 * mm, 60 * mm, 25 * mm, 75 * mm])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), VedomostColors.LIGHT_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 5 * mm))

    # -- Students Leaderboard Table -------------------------------------------
    table_headers = [
        Paragraph("<b>№</b>", styles["cell_bold_center"]),
        Paragraph("<b>O'quvchi F.I.Sh</b>", styles["cell_bold"]),
        Paragraph("<b>Listening</b>", styles["cell_bold_center"]),
        Paragraph("<b>Reading</b>", styles["cell_bold_center"]),
        Paragraph("<b>Writing</b>", styles["cell_bold_center"]),
        Paragraph("<b>Jami ball</b>", styles["cell_bold_center"]),
        Paragraph("<b>Foiz (%)</b>", styles["cell_bold_center"]),
        Paragraph("<b>CEFR / Band</b>", styles["cell_bold_center"]),
        Paragraph("<b>Natija</b>", styles["cell_bold_center"]),
        Paragraph("<b>Ustoz qaydi</b>", styles["cell"]),
    ]

    rows = [table_headers]

    # Sort students: those who took the test by percentage DESC, then non-participants
    sorted_students = sorted(
        group_students,
        key=lambda s: (
            float(student_attempt_map[s.id].percentage) if s.id in student_attempt_map else -1.0,
            float(student_attempt_map[s.id].score) if s.id in student_attempt_map else -1.0,
        ),
        reverse=True,
    )

    for idx, s in enumerate(sorted_students, start=1):
        s_name = s.get_full_name() or s.email
        att = student_attempt_map.get(s.id)

        if att:
            sec_scores = att.section_scores or {}
            # Extract section scores if available
            lis_val = "-"
            read_val = "-"
            wri_val = "-"

            for k, v in sec_scores.items():
                k_upper = str(k).upper()
                score_str = f"{v.get('earned', 0):g}" if isinstance(v, dict) else f"{v:g}"
                if "LIST" in k_upper:
                    lis_val = score_str
                elif "READ" in k_upper:
                    read_val = score_str
                elif "WRIT" in k_upper or "ESSAY" in k_upper:
                    wri_val = score_str

            band_lvl = att.cefr_level or (f"{att.band_score}" if att.band_score else att.rasch_grade or "-")
            status_text = "O'tdi" if att.is_passed else "Qoldi"
            status_color = VedomostColors.SUCCESS if att.is_passed else VedomostColors.DANGER

            note = att.teacher_comment[:30] + "..." if len(att.teacher_comment) > 30 else att.teacher_comment
            if not note and att.teacher_overridden:
                note = "Ustoz tasdiqlagan"

            rows.append([
                Paragraph(str(idx), styles["cell_center"]),
                Paragraph(s_name, styles["cell"]),
                Paragraph(lis_val, styles["cell_center"]),
                Paragraph(read_val, styles["cell_center"]),
                Paragraph(wri_val, styles["cell_center"]),
                Paragraph(f"<b>{att.score:g}</b>", styles["cell_center"]),
                Paragraph(f"<b>{att.percentage:.1f}%</b>", styles["cell_center"]),
                Paragraph(str(band_lvl), styles["cell_center"]),
                Paragraph(f"<font color='{status_color.hexval()}'><b>{status_text}</b></font>", styles["cell_center"]),
                Paragraph(note or "-", styles["cell"]),
            ])
        else:
            rows.append([
                Paragraph(str(idx), styles["cell_center"]),
                Paragraph(f"{s_name} <font color='#94a3b8'>(Qatnashmadi)</font>", styles["cell"]),
                Paragraph("-", styles["cell_center"]),
                Paragraph("-", styles["cell_center"]),
                Paragraph("-", styles["cell_center"]),
                Paragraph("0", styles["cell_center"]),
                Paragraph("0%", styles["cell_center"]),
                Paragraph("-", styles["cell_center"]),
                Paragraph("<font color='#64748b'>Topshirmadi</font>", styles["cell_center"]),
                Paragraph("-", styles["cell"]),
            ])

    col_widths = [10 * mm, 60 * mm, 20 * mm, 20 * mm, 20 * mm, 22 * mm, 22 * mm, 26 * mm, 24 * mm, 48 * mm]
    leaderboard_table = Table(rows, colWidths=col_widths, repeatRows=1)
    leaderboard_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VedomostColors.HEADER_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(leaderboard_table)
    story.append(Spacer(1, 6 * mm))

    # -- Signatures Footer ----------------------------------------------------
    footer_row = [
        Paragraph(f"<b>Hujjat sanasi:</b> {now_str}", styles["footer_text"]),
        Paragraph("<b>Ustoz imzosi:</b> __________________________", styles["cell"]),
        Paragraph("<b>O'quv bo'limi tasdig'i:</b> __________________________", styles["cell"]),
    ]
    footer_table = Table([footer_row], colWidths=[70 * mm, 100 * mm, 100 * mm])
    story.append(KeepTogether(footer_table))

    doc.build(story)
    logger.info("Group vedomost PDF generated: %s (group_id=%s)", file_path, group_id)
    return file_path


# ---------------------------------------------------------------------------
# 3. Single Student AI Essay Scorecard / Vedomost PDF
# ---------------------------------------------------------------------------
def generate_essay_vedomost_pdf(submission_or_id: Any) -> str:
    """
    Generates an official A4 portrait essay scorecard PDF and writes it to media/vedomost/.
    Returns the absolute path to the generated PDF.
    """
    from apps.essays.models import EssaySubmission
    from apps.essays.services import generate_essay_result_pdf

    if isinstance(submission_or_id, int):
        submission = EssaySubmission.objects.select_related("student", "topic").get(
            id=submission_or_id
        )
    else:
        submission = submission_or_id

    vedomost_dir = os.path.join(settings.MEDIA_ROOT, "vedomost")
    os.makedirs(vedomost_dir, exist_ok=True)
    filename = f"essay_vedomost_{submission.id}.pdf"
    file_path = os.path.join(vedomost_dir, filename)

    pdf_buffer = generate_essay_result_pdf(submission)
    pdf_bytes = pdf_buffer.getvalue() if hasattr(pdf_buffer, "getvalue") else bytes(pdf_buffer)
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    logger.info("Essay vedomost PDF generated: %s (submission_id=%s)", file_path, submission.id)
    return file_path


# ---------------------------------------------------------------------------
# 4. Single Student AI Speaking Scorecard / Vedomost PDF
# ---------------------------------------------------------------------------
def generate_speaking_vedomost_pdf(submission_or_id: Any) -> str:
    """
    Generates an official A4 portrait IELTS / CEFR Speaking scorecard PDF.
    Returns the absolute path to the generated PDF.
    """
    from django.utils.html import escape as _esc
    from apps.speaking.models import SpeakingSubmission

    if isinstance(submission_or_id, int):
        sub = SpeakingSubmission.objects.select_related("user", "topic").get(
            id=submission_or_id
        )
    else:
        sub = submission_or_id

    user = sub.user
    topic = sub.topic
    group = user.student_groups.first() if hasattr(user, "student_groups") else None
    group_name = group.name if group else "Mustaqil ta'lim (Individual)"
    student_name = user.get_full_name() or getattr(user, "username", "") or user.email

    vedomost_dir = os.path.join(settings.MEDIA_ROOT, "vedomost")
    os.makedirs(vedomost_dir, exist_ok=True)
    filename = f"speaking_vedomost_{sub.id}.pdf"
    file_path = os.path.join(vedomost_dir, filename)

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = _get_styles()
    story: list[Any] = []

    # -- Header ---------------------------------------------------------------
    story.append(Paragraph("GRAND EDUCATION LMS", styles["title"]))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "RASMIY AI SPEAKING VEDOMOSTI / OFFICIAL IELTS SPEAKING SCORECARD",
            styles["subtitle"],
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(
        HRFlowable(
            width="100%",
            thickness=1.5,
            color=VedomostColors.PRIMARY,
            spaceAfter=8,
        )
    )

    # -- Student & Speaking Task Meta Table -----------------------------------
    date_str = (
        sub.created_at.strftime("%d.%m.%Y %H:%M")
        if getattr(sub, "created_at", None)
        else timezone.now().strftime("%d.%m.%Y %H:%M")
    )
    part_label = topic.get_part_display() if hasattr(topic, "get_part_display") else str(getattr(topic, "part", "Part 2"))
    topic_title = getattr(topic, "title", "Speaking Prompt")

    meta_data = [
        [
            Paragraph("<b>O'quvchi F.I.Sh:</b>", styles["cell"]),
            Paragraph(_esc(student_name), styles["cell_bold"]),
            Paragraph("<b>Speaking mavzusi:</b>", styles["cell"]),
            Paragraph(_esc(topic_title), styles["cell_bold"]),
        ],
        [
            Paragraph("<b>Guruh:</b>", styles["cell"]),
            Paragraph(_esc(group_name), styles["cell"]),
            Paragraph("<b>Imtihon qismi:</b>", styles["cell"]),
            Paragraph(_esc(str(part_label)), styles["cell"]),
        ],
        [
            Paragraph("<b>Hujjat ID:</b>", styles["cell"]),
            Paragraph(f"SPK-{sub.id:06d}", styles["cell"]),
            Paragraph("<b>Nutq davomiyligi:</b>", styles["cell"]),
            Paragraph(f"{getattr(sub, 'duration_seconds', 60)} soniya", styles["cell"]),
        ],
        [
            Paragraph("<b>Topshirilgan sana:</b>", styles["cell"]),
            Paragraph(date_str, styles["cell"]),
            Paragraph("<b>Baholash tizimi:</b>", styles["cell"]),
            Paragraph("AI IELTS Examiner (Band 1.0–9.0)", styles["cell"]),
        ],
    ]

    meta_table = Table(meta_data, colWidths=[35 * mm, 55 * mm, 35 * mm, 55 * mm])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), VedomostColors.LIGHT_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 5 * mm))

    # -- Key Metrics Cards ----------------------------------------------------
    overall = float(getattr(sub, "overall_band", 0) or 0)
    fc = float(getattr(sub, "fluency_score", 0) or 0)
    lr = float(getattr(sub, "lexical_score", 0) or 0)
    gra = float(getattr(sub, "grammar_score", 0) or 0)
    pr = float(getattr(sub, "pronunciation_score", 0) or 0)

    cefr_map = "C2" if overall >= 8.5 else ("C1" if overall >= 7.0 else ("B2" if overall >= 5.5 else ("B1" if overall >= 4.0 else "A2")))

    metrics_data = [
        [
            Paragraph(f"Band {overall:.1f}", styles["metric_value"]),
            Paragraph(cefr_map, styles["metric_value"]),
            Paragraph(f"{fc:.1f} / {lr:.1f}", styles["metric_value"]),
            Paragraph(f"{gra:.1f} / {pr:.1f}", styles["metric_value"]),
        ],
        [
            Paragraph("OVERALL BAND", styles["metric_label"]),
            Paragraph("CEFR DARAJASI", styles["metric_label"]),
            Paragraph("FLUENCY / LEXICAL", styles["metric_label"]),
            Paragraph("GRAMMAR / PRONUN.", styles["metric_label"]),
        ],
    ]

    metrics_table = Table(metrics_data, colWidths=[45 * mm, 45 * mm, 45 * mm, 45 * mm])
    metrics_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 1, VedomostColors.SECONDARY),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(metrics_table)
    story.append(Spacer(1, 6 * mm))

    # -- 4 Criteria Table -----------------------------------------------------
    story.append(
        Paragraph(
            "4 RASMIY IELTS SPEAKING MEZONLARI TAHLILI (CRITERIA BREAKDOWN)",
            styles["section_heading"],
        )
    )

    fb = getattr(sub, "feedback", {}) or {}
    criteria_rows = [
        [
            Paragraph("<b>Mezon (Criterion)</b>", styles["cell_bold"]),
            Paragraph("<b>Ball (Band)</b>", styles["cell_bold_center"]),
            Paragraph("<b>Maksimal</b>", styles["cell_bold_center"]),
            Paragraph("<b>Ekspert izohi</b>", styles["cell_bold"]),
        ],
        [
            Paragraph("1. Fluency and Coherence (FC)", styles["cell"]),
            Paragraph(f"<b>{fc:.1f}</b>", styles["cell_center"]),
            Paragraph("9.0", styles["cell_center"]),
            Paragraph(_esc(str(fb.get("fluency_feedback") or "Nutq ravonligi va mantiqiy izchilligi baholandi.")[:220]), styles["cell"]),
        ],
        [
            Paragraph("2. Lexical Resource (LR)", styles["cell"]),
            Paragraph(f"<b>{lr:.1f}</b>", styles["cell_center"]),
            Paragraph("9.0", styles["cell_center"]),
            Paragraph(_esc(str(fb.get("lexical_feedback") or "So'z boyligi va akademik iboralar qo'llanilishi baholandi.")[:220]), styles["cell"]),
        ],
        [
            Paragraph("3. Grammatical Range & Accuracy (GRA)", styles["cell"]),
            Paragraph(f"<b>{gra:.1f}</b>", styles["cell_center"]),
            Paragraph("9.0", styles["cell_center"]),
            Paragraph(_esc(str(fb.get("grammar_feedback") or "Grammatik qurilmalar xilma-xilligi va aniqligi baholandi.")[:220]), styles["cell"]),
        ],
        [
            Paragraph("4. Pronunciation & Intonation (PR)", styles["cell"]),
            Paragraph(f"<b>{pr:.1f}</b>", styles["cell_center"]),
            Paragraph("9.0", styles["cell_center"]),
            Paragraph(_esc(str(fb.get("pronunciation_feedback") or "Talaffuz va intonatsiya aniqligi baholandi.")[:220]), styles["cell"]),
        ],
    ]

    crit_table = Table(criteria_rows, colWidths=[55 * mm, 22 * mm, 22 * mm, 81 * mm])
    crit_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VedomostColors.HEADER_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    story.append(crit_table)
    story.append(Spacer(1, 5 * mm))

    # -- Summary & Transcript -------------------------------------------------
    story.append(Paragraph("EKSPERT XULOSASI VA NUTQ MATNI (SUMMARY & TRANSCRIPT)", styles["section_heading"]))
    summary_text = _esc(str(fb.get("summary") or "Speaking topshirig'i muvaffaqiyatli yakunlandi.")[:600])
    transcript_text = _esc(str(getattr(sub, "transcript", "") or "")[:600])

    diag_paragraphs = [
        Paragraph(f"<b>Umumiy xulosa:</b> {summary_text}", styles["cell"]),
    ]
    if transcript_text:
        diag_paragraphs.append(Spacer(1, 2 * mm))
        diag_paragraphs.append(Paragraph(f"<b>Transcript (Nutq matni):</b> <i>{transcript_text}</i>", styles["footer_text"]))

    diag_table = Table([[diag_paragraphs]], colWidths=[180 * mm])
    diag_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), VedomostColors.LIGHT_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, VedomostColors.BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(diag_table)
    story.append(Spacer(1, 6 * mm))

    # -- Verification & QR Code -----------------------------------------------
    base_url = getattr(settings, "SITE_URL", "https://grandec.uz").rstrip("/")
    verify_url = f"{base_url}/speaking"
    qr_img = _generate_qr_code(verify_url, size=2.2 * cm)

    sig_col1 = [
        Paragraph("<b>Grand Education LMS — AI Speaking Assessment</b>", styles["cell"]),
        Spacer(1, 2 * mm),
        Paragraph(f"Hujjat sanasi: {timezone.now().strftime('%d.%m.%Y %H:%M')}", styles["footer_text"]),
        Paragraph(f"Tekshirish kodi: SPK-{sub.id:06d}-B{overall:.1f}", styles["footer_text"]),
    ]
    sig_table = Table([[sig_col1, qr_img if qr_img else Paragraph("", styles["cell"])]], colWidths=[140 * mm, 40 * mm])
    sig_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ])
    )
    story.append(KeepTogether(sig_table))

    doc.build(story)
    logger.info("Speaking vedomost PDF generated: %s (submission_id=%s)", file_path, sub.id)
    return file_path

