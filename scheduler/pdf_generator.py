"""
pdf_generator.py - PDF Export using ReportLab
AI-Based Intelligent Faculty Workload and Scheduling System

Generates:
  1. Full Timetable PDF (grid view)
  2. Workload Summary PDF (bar chart equivalent in PDF table form)
  3. Faculty personal schedule PDF
"""

import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from .models import TimetableEntry, WorkloadLog, ScheduleVersion, Faculty, TimeSlot


# ─── Color Palette ────────────────────────────────────────────────────────────
PRIMARY   = colors.HexColor('#1e3a5f')
SECONDARY = colors.HexColor('#2d6a9f')
ACCENT    = colors.HexColor('#4CAF50')
LIGHT_BG  = colors.HexColor('#f0f4f8')
ALT_ROW   = colors.HexColor('#dce8f5')
WHITE     = colors.white
HEADER_TXT = colors.white


def _get_active_version():
    return ScheduleVersion.objects.filter(is_active=True).first()


def generate_timetable_pdf(version_number=None):
    """
    Generate full timetable as PDF. Returns bytes buffer.
    Organized as: Day × Period grid with faculty/course/room info.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Title'],
        textColor=PRIMARY, fontSize=18, spaceAfter=6
    )
    sub_style = ParagraphStyle(
        'Sub', parent=styles['Normal'],
        textColor=SECONDARY, fontSize=10, spaceAfter=12
    )
    cell_style = ParagraphStyle(
        'Cell', parent=styles['Normal'],
        fontSize=7, leading=9
    )

    if version_number is None:
        v = _get_active_version()
        version_number = v.version_number if v else 1

    entries = TimetableEntry.objects.filter(
        schedule_version=version_number
    ).select_related('faculty', 'course', 'classroom', 'timeslot').order_by(
        'timeslot__day', 'timeslot__period'
    )

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    periods = list(TimeSlot.objects.values_list('period', flat=True).distinct().order_by('period'))

    # Build lookup: {(day, period): [entries]}
    lookup = {}
    for e in entries:
        key = (e.timeslot.day, e.timeslot.period)
        lookup.setdefault(key, []).append(e)

    # Build table data
    header_row = ['Day / Period'] + [f'Period {p}' for p in periods]
    table_data = [header_row]

    for day in days:
        row = [Paragraph(f'<b>{day}</b>', cell_style)]
        for period in periods:
            cell_entries = lookup.get((day, period), [])
            if cell_entries:
                lines = []
                for e in cell_entries:
                    lines.append(
                        f"<b>{e.course.course_name[:18]}</b><br/>"
                        f"{e.faculty.name}<br/>"
                        f"<i>{e.classroom.room_name}</i>"
                    )
                row.append(Paragraph('<br/>───<br/>'.join(lines), cell_style))
            else:
                row.append(Paragraph('—', cell_style))
        table_data.append(row)

    col_width = (landscape(A4)[0] - 3*cm) / (len(periods) + 1)
    col_widths = [2.5*cm] + [col_width] * len(periods)

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0),  PRIMARY),
        ('TEXTCOLOR',    (0, 0), (-1, 0),  WHITE),
        ('FONTNAME',     (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, 0),  9),
        ('BACKGROUND',   (0, 1), (0, -1),  SECONDARY),
        ('TEXTCOLOR',    (0, 1), (0, -1),  WHITE),
        ('ROWBACKGROUNDS', (1, 1), (-1, -1), [WHITE, ALT_ROW]),
        ('GRID',         (0, 0), (-1, -1), 0.5, colors.HexColor('#b0c4de')),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',        (0, 0), (0, -1),  'CENTER'),
        ('FONTSIZE',     (1, 1), (-1, -1), 7),
        ('PADDING',      (0, 0), (-1, -1), 4),
    ]))

    elements = [
        Paragraph("AI-Based Intelligent Faculty Workload & Scheduling System", title_style),
        Paragraph(f"Generated Timetable — Schedule Version {version_number}", sub_style),
        HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=12),
        tbl,
    ]

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_workload_pdf(version_number=None):
    """
    Generate workload summary PDF with bar chart and table.
    Returns bytes buffer.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('T', parent=styles['Title'], textColor=PRIMARY, fontSize=16)
    sub_style   = ParagraphStyle('S', parent=styles['Normal'], textColor=SECONDARY, fontSize=10)

    if version_number is None:
        v = _get_active_version()
        version_number = v.version_number if v else 1

    logs = WorkloadLog.objects.filter(
        schedule_version=version_number
    ).select_related('faculty').order_by('-utilization_percent')

    # ── Bar Chart ─────────────────────────────────────────────────────────────
    drawing = Drawing(450, 200)
    bc = VerticalBarChart()
    bc.x = 40
    bc.y = 20
    bc.width = 380
    bc.height = 160
    bc.data = [[log.utilization_percent for log in logs]]
    bc.categoryAxis.categoryNames = [log.faculty.name[:12] for log in logs]
    bc.categoryAxis.labels.angle = 30
    bc.categoryAxis.labels.fontSize = 7
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 120
    bc.valueAxis.valueStep = 20
    bc.bars[0].fillColor = SECONDARY
    drawing.add(bc)

    # ── Summary Table ─────────────────────────────────────────────────────────
    table_data = [
        [
            Paragraph('<b>Faculty Name</b>', styles['Normal']),
            Paragraph('<b>Department</b>', styles['Normal']),
            Paragraph('<b>Assigned Hrs</b>', styles['Normal']),
            Paragraph('<b>Max Hrs</b>', styles['Normal']),
            Paragraph('<b>Utilization %</b>', styles['Normal']),
            Paragraph('<b>Status</b>', styles['Normal']),
        ]
    ]

    for log in logs:
        status = "✔ Balanced"
        status_color = ACCENT
        if log.utilization_percent > 90:
            status = "⚠ Overloaded"
            status_color = colors.red
        elif log.utilization_percent < 40:
            status = "↓ Underused"
            status_color = colors.orange

        table_data.append([
            log.faculty.name,
            log.faculty.department or '—',
            str(log.assigned_hours),
            str(log.max_hours),
            f"{log.utilization_percent:.1f}%",
            Paragraph(f'<font color="{status_color.hexval()}">{status}</font>', styles['Normal']),
        ])

    col_w = [4.5*cm, 3*cm, 2.5*cm, 2.5*cm, 2.5*cm, 3*cm]
    tbl = Table(table_data, colWidths=col_w)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0),  PRIMARY),
        ('TEXTCOLOR',    (0, 0), (-1, 0),  WHITE),
        ('GRID',         (0, 0), (-1, -1), 0.5, colors.HexColor('#b0c4de')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, ALT_ROW]),
        ('FONTSIZE',     (0, 0), (-1, -1),  8),
        ('PADDING',      (0, 0), (-1, -1),  6),
    ]))

    elements = [
        Paragraph("Faculty Workload Summary Report", title_style),
        Paragraph(f"Schedule Version {version_number} — Workload Distribution Analysis", sub_style),
        HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=12),
        Paragraph("Workload Utilization Chart (%)", styles['Heading2']),
        drawing,
        Spacer(1, 0.5*cm),
        Paragraph("Detailed Workload Table", styles['Heading2']),
        Spacer(1, 0.3*cm),
        tbl,
    ]

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_faculty_schedule_pdf(faculty_id, version_number=None):
    """
    Generate individual faculty schedule PDF.
    Returns bytes buffer.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('T', parent=styles['Title'], textColor=PRIMARY, fontSize=16)

    try:
        faculty = Faculty.objects.get(id=faculty_id)
    except Faculty.DoesNotExist:
        return buffer

    if version_number is None:
        v = _get_active_version()
        version_number = v.version_number if v else 1

    entries = TimetableEntry.objects.filter(
        faculty=faculty, schedule_version=version_number
    ).select_related('course', 'classroom', 'timeslot').order_by(
        'timeslot__day', 'timeslot__period'
    )

    table_data = [[
        Paragraph('<b>Day</b>', styles['Normal']),
        Paragraph('<b>Period</b>', styles['Normal']),
        Paragraph('<b>Time</b>', styles['Normal']),
        Paragraph('<b>Course</b>', styles['Normal']),
        Paragraph('<b>Room</b>', styles['Normal']),
    ]]

    for e in entries:
        table_data.append([
            e.timeslot.day,
            f"Period {e.timeslot.period}",
            f"{e.timeslot.start_time.strftime('%H:%M')} - {e.timeslot.end_time.strftime('%H:%M')}",
            e.course.course_name,
            e.classroom.room_name,
        ])

    col_w = [3*cm, 2.5*cm, 3.5*cm, 6*cm, 3*cm]
    tbl = Table(table_data, colWidths=col_w)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0),  PRIMARY),
        ('TEXTCOLOR',    (0, 0), (-1, 0),  WHITE),
        ('GRID',         (0, 0), (-1, -1), 0.5, colors.HexColor('#b0c4de')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, ALT_ROW]),
        ('FONTSIZE',     (0, 0), (-1, -1), 9),
        ('PADDING',      (0, 0), (-1, -1), 6),
    ]))

    wl = WorkloadLog.objects.filter(faculty=faculty, schedule_version=version_number).first()
    wl_text = f"Assigned: {wl.assigned_hours}h / {wl.max_hours}h ({wl.utilization_percent:.1f}%)" if wl else ""

    elements = [
        Paragraph(f"Personal Schedule — {faculty.name}", title_style),
        Paragraph(f"{faculty.department} | {wl_text}", styles['Normal']),
        HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=12),
        tbl,
    ]

    doc.build(elements)
    buffer.seek(0)
    return buffer
