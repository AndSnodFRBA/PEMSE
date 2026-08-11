"""Nebraska DHHS course-completion report PDF, ready to submit per 172 NAC 13-004(D)."""
import io

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .pdf import BORDER, LIGHT, NAVY, _footer

PEMSE_ADDRESS = '709 Rosedale Dr., Scottsbluff, NE 69361'
PEMSE_PHONE   = '308.631.2424'
PEMSE_EMAIL   = 'emseducation19@gmail.com'
SIGNER_NAME   = 'Robin Darnall'
SIGNER_TITLE  = 'Program Director'


def generate_dhhs_report(report):
    """report: a students.models.CourseReportRecord instance."""
    course = report.course

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.85 * inch,
    )

    styles = getSampleStyleSheet()
    h1     = ParagraphStyle('h1', parent=styles['Heading1'], textColor=NAVY, fontSize=15, alignment=1, spaceAfter=2)
    sub    = ParagraphStyle('sub', parent=styles['Normal'], fontSize=11, alignment=1, textColor=NAVY, spaceAfter=2)
    ref    = ParagraphStyle('ref', parent=styles['Normal'], fontSize=9, alignment=1, textColor=colors.HexColor('#6b7280'))
    deadline_note = ParagraphStyle('deadline', parent=styles['Normal'], fontSize=9, alignment=1, textColor=colors.HexColor('#c0392b'), spaceAfter=6)
    h2     = ParagraphStyle('h2', parent=styles['Heading2'], textColor=NAVY, fontSize=11, spaceBefore=14, spaceAfter=4)
    body   = ParagraphStyle('body', parent=styles['Normal'], fontSize=9, leading=13)
    small_gray = ParagraphStyle('small_gray', parent=body, textColor=colors.HexColor('#888888'), fontSize=8)
    label_style = ParagraphStyle('label', parent=body, fontName='Helvetica-Bold')
    value_style = ParagraphStyle('value', parent=body)

    def section(title):
        return [Paragraph(title, h2), Spacer(1, 4)]

    def kv_table(rows):
        # Wrap cell text in Paragraphs so long labels wrap within the column
        # instead of overflowing into the value column.
        wrapped = [[Paragraph(label, label_style), Paragraph(value, value_style)] for label, value in rows]
        t = Table(wrapped, colWidths=[2.25 * inch, 4.5 * inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), LIGHT),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('GRID',       (0, 0), (-1, -1), 0.5, BORDER),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, LIGHT]),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ]))
        return t

    story = [
        Paragraph('Nebraska Department of Health and Human Services', h1),
        Paragraph('Emergency Medical Services Training Agency — Course Completion Report', sub),
        Paragraph('172 NAC Chapter 13 Section 004(D)', ref),
        Paragraph('Required within 30 days of course completion', deadline_note),
        HRFlowable(width='100%', thickness=1, color=NAVY),
    ]

    # ── Section 1: Training Agency Information ────────────────────────────
    story += section('1. Training Agency Information')
    story.append(kv_table([
        ['Agency Name', report.training_agency_name or 'Panhandle EMS Education'],
        ['Address', PEMSE_ADDRESS],
        ['Phone', PEMSE_PHONE],
        ['Email', PEMSE_EMAIL],
    ]))

    # ── Section 2: Course Information ──────────────────────────────────────
    story += section('2. Course Information')
    story.append(kv_table([
        ['Course', f'Option {course.option_number} — {course.name}'],
        ['Licensure Level', course.get_licensure_display() if course.licensure else '—'],
        ['Course Location', report.course_location or course.location_display or '—'],
        ['Start Date', course.start_date.strftime('%B %d, %Y') if course.start_date else '—'],
        ['End Date', course.end_date.strftime('%B %d, %Y') if course.end_date else '—'],
        ['Instructor(s)', report.instructor_names or '—'],
    ]))

    # ── Section 3: Enrollment Statistics ───────────────────────────────────
    story += section('3. Enrollment Statistics')
    story.append(kv_table([
        ['Students Enrolled', str(report.students_enrolled)],
        ['Students Withdrew Prior to Completion', str(report.students_withdrew)],
        ['Students Completed', str(report.students_completed)],
    ]))

    # ── Section 4: Hours — 172 NAC 13-004(D)(vii) ──────────────────────────
    story += section('4. Hours — Per 172 NAC 13-004(D)(vii)')
    is_aemt = course.licensure in ('AEMT', 'PARA')
    hour_rows = [['Total Didactic Hours', str(report.total_didactic_hours)]]
    if is_aemt:
        hour_rows += [
            ['Total Clinical Hours (AEMT/Paramedic)', str(report.total_clinical_hours)],
            ['Total Field Internship Hours (AEMT/Paramedic)', str(report.total_field_hours)],
        ]
    story.append(kv_table(hour_rows))

    # ── Section 5: Certification ────────────────────────────────────────────
    story += section('5. Certification')
    story.append(Paragraph(
        'I certify that the information provided is accurate and complete.',
        body,
    ))
    story.append(Spacer(1, 30))
    story.append(Paragraph(f'Signature: _________________________________  ({SIGNER_NAME})', body))
    story.append(Spacer(1, 14))
    story.append(Paragraph(f'Name: {SIGNER_NAME}', body))
    story.append(Paragraph(f'Title: {SIGNER_TITLE}', body))
    story.append(Paragraph('Date: ______________', body))

    story.append(Spacer(1, 20))
    story.append(Paragraph(f'Report generated {timezone.now().strftime("%B %d, %Y")}', small_gray))
    story.append(Paragraph(f'PEMSE portal reference: DEPTRPT-{report.pk:06d}', small_gray))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf.getvalue()
