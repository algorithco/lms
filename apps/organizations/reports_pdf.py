"""
White-Label Monthly Report PDF Generator (apps/organizations/reports_pdf.py).

Produces professional A4 PDF reports for parent-teacher meetings and academy directors
incorporating the learning center's custom logo, name, brand color, and stamp/signature.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_monthly_group_report_pdf(
    group,
    branding: Dict[str, Any],
    roster_data: List[Dict[str, Any]],
    summary_stats: Dict[str, Any],
) -> bytes:
    """Generate professional A4 PDF monthly report using ReportLab."""
    buffer = io.BytesIO()

    # Page setup: A4 portrait, 15mm margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    brand_hex = branding.get("brand_color") or "#0F766E"
    try:
        brand_color = colors.HexColor(brand_hex)
    except Exception:
        brand_color = colors.HexColor("#0F766E")

    header_style = ParagraphStyle(
        "HeaderTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.white,
    )
    header_subtitle = ParagraphStyle(
        "HeaderSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#CCFBF1"),
    )
    card_title_style = ParagraphStyle(
        "CardTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#64748B"),
    )
    card_value_style = ParagraphStyle(
        "CardValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=16,
        textColor=brand_color,
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1,  # Center
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1E293B"),
    )
    table_cell_center = ParagraphStyle(
        "TableCellCenter",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1E293B"),
        alignment=1,
    )

    story = []

    # 1. Top Header Banner with Brand Color
    center_name = branding.get("center_name") or "GRAND EDUCATION HAMKOR MARKAZI"
    header_title = branding.get("header_title") or "OYLIK AKADEMIK TAHLIL VA NATIJALAR HISOBOTI"
    group_name = getattr(group, "name", "Guruh")
    teacher_name = (
        getattr(group, "teacher", None).get_full_name()
        if getattr(group, "teacher", None)
        else "O'qituvchi"
    )
    today_str = timezone.now().strftime("%d.%m.%Y")

    banner_data = [
        [
            Paragraph(f"<b>{center_name.upper()}</b>", header_style),
            Paragraph(f"Sana: <b>{today_str}</b>", header_subtitle),
        ],
        [
            Paragraph(f"{header_title}<br/>Guruh: <b>{group_name}</b> | Ustoz: <b>{teacher_name}</b>", header_subtitle),
            Paragraph("Rasmiy hisobot", header_subtitle),
        ],
    ]

    banner_table = Table(banner_data, colWidths=[130 * mm, 50 * mm])
    banner_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), brand_color),
            ("PADDING", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    story.append(banner_table)
    story.append(Spacer(1, 10))

    # 2. Key Metrics Summary Cards Row (4 blocks)
    total_students = summary_stats.get("total_students", len(roster_data))
    avg_attendance = summary_stats.get("avg_attendance", 0.0)
    avg_test_score = summary_stats.get("avg_test_score", 0.0)
    total_essays = summary_stats.get("total_essays", 0)

    metric_cards = [
        [
            Paragraph("JAMI O'QUVCHILAR", card_title_style),
            Paragraph("O'RTACHA DAVOMAT", card_title_style),
            Paragraph("O'RTACHA TEST BALI", card_title_style),
            Paragraph("TOPSHIRILGAN ESSELAR", card_title_style),
        ],
        [
            Paragraph(f"{total_students} nafar", card_value_style),
            Paragraph(f"{avg_attendance}%", card_value_style),
            Paragraph(f"{avg_test_score}%", card_value_style),
            Paragraph(f"{total_essays} ta", card_value_style),
        ],
    ]

    metrics_table = Table(metric_cards, colWidths=[45 * mm, 45 * mm, 45 * mm, 45 * mm])
    metrics_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ])
    )
    story.append(metrics_table)
    story.append(Spacer(1, 12))

    # 3. Main Student Performance Table
    table_rows = [
        [
            Paragraph("№", table_header_style),
            Paragraph("O'quvchi F.I.Sh.", table_header_style),
            Paragraph("Davomat", table_header_style),
            Paragraph("Ishlangan testlar", table_header_style),
            Paragraph("O'rtacha ball", table_header_style),
            Paragraph("Esse ko'rsatkichi", table_header_style),
            Paragraph("Umumiy baho", table_header_style),
        ]
    ]

    for idx, student in enumerate(roster_data, start=1):
        name = student.get("name", f"O'quvchi #{idx}")
        att = f"{student.get('attendance_rate', 0)}%"
        tests_count = f"{student.get('tests_taken', 0)} ta"
        score = f"{student.get('avg_score', 0)}%"
        essays = f"{student.get('essays_done', 0)} ta"
        grade = student.get("overall_grade", "Yaxshi")

        table_rows.append([
            Paragraph(str(idx), table_cell_center),
            Paragraph(f"<b>{name}</b>", table_cell_style),
            Paragraph(att, table_cell_center),
            Paragraph(tests_count, table_cell_center),
            Paragraph(score, table_cell_center),
            Paragraph(essays, table_cell_center),
            Paragraph(f"<b>{grade}</b>", table_cell_center),
        ])

    perf_table = Table(
        table_rows,
        colWidths=[10 * mm, 52 * mm, 22 * mm, 25 * mm, 23 * mm, 24 * mm, 24 * mm],
    )
    perf_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ])
    )
    story.append(perf_table)
    story.append(Spacer(1, 20))

    # 4. Stamp, Signature and Official Verification Footer (KeepTogether)
    stamp_path = branding.get("stamp_signature_path")
    footer_elements = []
    footer_elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=10))

    stamp_cell = Paragraph(
        f"Ustoz: <b>{teacher_name}</b><br/>Imzo: _______________<br/>M.O'.",
        table_cell_center,
    )
    if stamp_path:
        try:
            import os
            if os.path.exists(stamp_path):
                stamp_cell = RLImage(stamp_path, width=35 * mm, height=20 * mm)
        except Exception:
            pass

    footer_data = [
        [
            Paragraph(
                f"<b>{center_name}</b> rahbariyati va fan ustozi tomonidan tasdiqlandi.<br/>"
                f"Ushbu hujjat elektron tarzda shakllantirilgan va haqiqiy hisoblanadi.<br/>"
                f"<font color='#64748B' size='7'>Hujjat ID: #{getattr(group, 'id', 1)}-{timezone.now().strftime('%Y%m%d%H%M')}</font>",
                table_cell_style,
            ),
            stamp_cell,
        ]
    ]

    footer_table = Table(footer_data, colWidths=[120 * mm, 60 * mm])
    footer_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 4),
        ])
    )
    footer_elements.append(footer_table)

    story.append(KeepTogether(footer_elements))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
