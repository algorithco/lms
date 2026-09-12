"""
PDF Certificate Generator — ReportLab based.

Generates professional A4 landscape certificates with:
    - Decorative border and header
    - Student name, course title, score percentage
    - Certificate number and date
    - QR code for verification
    - Official branding elements

Architecture:
    - Single Responsibility: only generates PDF bytes.
    - Does NOT handle model saves — caller is responsible.
    - QR code links to /api/certificates/verify/{number}/ for authenticity check.
"""
from __future__ import annotations

import io
import os
from io import BytesIO
from typing import Any

from django.conf import settings
from django.utils import timezone

# ReportLab imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)

# QR code generation
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

class CertificateColors:
    """Professional certificate color scheme."""

    PRIMARY = colors.HexColor("#1a365d")       # Dark navy
    SECONDARY = colors.HexColor("#2c5282")     # Medium blue
    ACCENT = colors.HexColor("#d69e2e")        # Gold
    LIGHT_BG = colors.HexColor("#f7fafc")      # Light gray
    TEXT_DARK = colors.HexColor("#1a202c")      # Near black
    TEXT_LIGHT = colors.HexColor("#718096")     # Gray
    BORDER = colors.HexColor("#e2e8f0")         # Light border
    SUCCESS = colors.HexColor("#38a169")        # Green
    DECORATIVE = colors.HexColor("#bee3f8")     # Light blue


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _get_styles() -> dict[str, ParagraphStyle]:
    """Certificate uchun matn uslublari."""
    styles = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "CertTitle",
            parent=styles["Title"],
            fontSize=28,
            leading=34,
            textColor=CertificateColors.PRIMARY,
            spaceAfter=6,
            alignment=1,  # CENTER
        ),
        "subtitle": ParagraphStyle(
            "CertSubtitle",
            parent=styles["Normal"],
            fontSize=14,
            leading=18,
            textColor=CertificateColors.SECONDARY,
            spaceAfter=4,
            alignment=1,
        ),
        "student_name": ParagraphStyle(
            "StudentName",
            parent=styles["Title"],
            fontSize=22,
            leading=28,
            textColor=CertificateColors.ACCENT,
            spaceBefore=12,
            spaceAfter=12,
            alignment=1,
        ),
        "body": ParagraphStyle(
            "CertBody",
            parent=styles["Normal"],
            fontSize=12,
            leading=16,
            textColor=CertificateColors.TEXT_DARK,
            alignment=1,
        ),
        "detail": ParagraphStyle(
            "CertDetail",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=CertificateColors.TEXT_LIGHT,
            alignment=1,
        ),
        "footer": ParagraphStyle(
            "CertFooter",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=CertificateColors.TEXT_LIGHT,
            alignment=1,
        ),
        "score": ParagraphStyle(
            "CertScore",
            parent=styles["Title"],
            fontSize=36,
            leading=42,
            textColor=CertificateColors.SUCCESS,
            alignment=1,
        ),
    }


# ---------------------------------------------------------------------------
# QR Code generator
# ---------------------------------------------------------------------------

def _generate_qr_code(url: str, size: int = 100) -> Any:
    """
    QR kod generatsiya qilish.

    Args:
        url: QR kod ichidagi URL (verify endpoint).
        size: QR kod hajmi (pixel).

    Returns:
        ReportLab Image object yoki None.
    """
    if not HAS_QRCODE:
        return None

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # BytesIO ga saqlash
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return Image(buffer, width=size, height=size)


# ---------------------------------------------------------------------------
# Main PDF generator
# ---------------------------------------------------------------------------

def generate_certificate_pdf(
    certificate_number: str,
    student_full_name: str,
    course_title: str,
    test_title: str,
    percentage: float,
    issued_at: Any,
    verify_url: str,
) -> bytes:
    """
    Professional PDF sertifikat generatsiya qilish.

    Args:
        certificate_number: Noyob raqam (LMS-2026-000042).
        student_full_name: O'quvchining to'liq ismi.
        course_title: Kurs nomi.
        test_title: Test nomi.
        percentage: Olingan foiz (0-100).
        issued_at: Berilgan sana.
        verify_url: Tekshirish URL'i (QR code uchun).

    Returns:
        PDF faylning byte content.
    """
    buffer = BytesIO()

    # -- Document setup -----------------------------------------------------
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = _get_styles()
    elements: list[Any] = []

    # -- Decorative top line ------------------------------------------------
    elements.append(Spacer(1, 0.5 * cm))

    # -- Header: "CERTIFICATE OF COMPLETION" --------------------------------
    elements.append(Paragraph(
        "SERTIFIKAT",
        styles["title"],
    ))
    elements.append(Paragraph(
        "O'QUVNI TAMOMLASH HAQIDA",
        styles["subtitle"],
    ))

    elements.append(Spacer(1, 0.8 * cm))

    # -- Decorative separator -----------------------------------------------
    separator_data = [["", "", ""]]
    separator_table = Table(separator_data, colWidths=[6 * cm, 3 * cm, 6 * cm])
    separator_table.setStyle(TableStyle([
        ("LINEABOVE", (1, 0), (1, 0), 2, CertificateColors.ACCENT),
        ("LINEBELOW", (1, 0), (1, 0), 2, CertificateColors.ACCENT),
    ]))
    elements.append(separator_table)

    elements.append(Spacer(1, 0.5 * cm))

    # -- Body text ----------------------------------------------------------
    elements.append(Paragraph(
        "Ushbu sertifikat quyidagi o'quvchiga beriladi:",
        styles["body"],
    ))

    elements.append(Spacer(1, 0.3 * cm))

    # -- Student name (large, gold) -----------------------------------------
    elements.append(Paragraph(
        f"<b>{student_full_name}</b>",
        styles["student_name"],
    ))

    elements.append(Spacer(1, 0.3 * cm))

    # -- Course details -----------------------------------------------------
    elements.append(Paragraph(
        f'"{course_title}" kursini muvaffaqiyatli tamomladi',
        styles["body"],
    ))
    elements.append(Paragraph(
        f"Test: {test_title}",
        styles["body"],
    ))

    elements.append(Spacer(1, 0.8 * cm))

    # -- Score display ------------------------------------------------------
    score_data = [
        [Paragraph(f"<b>{percentage:.1f}%</b>", styles["score"]), ""],
        ["Olingan ball", ""],
    ]
    score_table = Table(score_data, colWidths=[8 * cm, 8 * cm])
    score_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (0, 0), 1, CertificateColors.BORDER),
    ]))
    elements.append(score_table)

    elements.append(Spacer(1, 1 * cm))

    # -- Footer: certificate number + date + QR ----------------------------
    footer_data = [
        [
            Paragraph(
                f"<b>Sertifikat raqami:</b><br/>{certificate_number}",
                styles["detail"],
            ),
            Paragraph(
                f"<b>Sana:</b><br/>{issued_at.strftime('%d.%m.%Y')}",
                styles["detail"],
            ),
            _generate_qr_code(verify_url, size=80) or Paragraph(
                "[QR Code]",
                styles["detail"],
            ),
        ],
    ]
    footer_table = Table(footer_data, colWidths=[6 * cm, 6 * cm, 4 * cm])
    footer_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, 0), (-1, 0), 1, CertificateColors.BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(footer_table)

    # -- Verification note --------------------------------------------------
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(Paragraph(
        f"Sertifikatni tekshirish: {verify_url}",
        styles["footer"],
    ))
    elements.append(Paragraph(
        "Ona Tili & Adabiyot — Online Test & Learning Management System",
        styles["footer"],
    ))

    # -- Build PDF ----------------------------------------------------------
    doc.build(elements)

    # bytes qaytarish
    buffer.seek(0)
    return buffer.getvalue()
