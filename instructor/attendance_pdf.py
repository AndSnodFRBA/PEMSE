"""Print-ready attendance roster PDF for a single class session."""
import io

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from django.contrib.staticfiles import finders

from students.pdf import BORDER, GRAY, LIGHT, NAVY, _footer

STATUS_ORDER = ['present', 'absent', 'late', 'excused', 'makeup']


def generate_attendance_pdf(session):
    """session: an instructor.models.AttendanceRecord instance."""
    from reportlab.lib import colors

    attendances = session.student_attendance.select_related('student').order_by(
        'student__last_name', 'student__first_name'
    )
    counts = {status: attendances.filter(status=status).count() for status in STATUS_ORDER}
    total = attendances.count()
    present_like = counts['present'] + counts['late'] + counts['makeup']
    attendance_pct = round(present_like / total * 100) if total else 0

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.85 * inch,
    )

    styles = getSampleStyleSheet()
    h1  = ParagraphStyle('h1', parent=styles['Heading1'], textColor=NAVY, fontSize=16, spaceAfter=4)
    h2  = ParagraphStyle('h2', parent=styles['Heading2'], textColor=NAVY, fontSize=11, spaceBefore=14, spaceAfter=4)
    sub = ParagraphStyle('sub', parent=styles['Normal'], textColor=GRAY, fontSize=10)
    body = ParagraphStyle('body', parent=styles['Normal'], fontSize=9, leading=13)

    def section(title):
        return [Paragraph(title, h2), Spacer(1, 4)]

    def kv_table(rows):
        t = Table(rows, colWidths=[2 * inch, 4.75 * inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), LIGHT),
            ('FONTNAME',   (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 9),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('GRID',       (0, 0), (-1, -1), 0.5, BORDER),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, LIGHT]),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ]))
        return t

    story = []

    # ── Header with logo ──────────────────────────────────────────────────
    title_block = [Paragraph('Panhandle EMS Education', h1), Paragraph('Attendance Roster', sub)]
    logo_path = finders.find('images/PEMSE.jpg')
    if logo_path:
        header_table = Table(
            [[RLImage(logo_path, width=0.6 * inch, height=0.6 * inch), title_block]],
            colWidths=[0.8 * inch, 5.95 * inch],
        )
        header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
        story.append(header_table)
    else:
        story += title_block
    story.append(Spacer(1, 10))

    # ── Session info ───────────────────────────────────────────────────────
    story += section('Session')
    location = session.calendar_event.location if session.calendar_event and session.calendar_event.location else '—'
    time_range = '—'
    if session.session_start:
        time_range = session.session_start.strftime('%I:%M %p')
        if session.session_end:
            time_range += f' – {session.session_end.strftime("%I:%M %p")}'
    story.append(kv_table([
        ['Course', f'Option {session.course.option_number} — {session.course.name}'],
        ['Date', session.session_date.strftime('%A, %B %d, %Y')],
        ['Type', session.get_session_type_display()],
        ['Topic', session.session_topic or '—'],
        ['Time', time_range],
        ['Location', location],
        ['Instructor', session.instructor.get_full_name()],
    ]))

    # ── Attendance table ───────────────────────────────────────────────────
    story += section('Attendance')
    rows = [['#', 'Student Name', 'Status', 'Arrival Time', 'Notes']]
    for i, att in enumerate(attendances, start=1):
        rows.append([
            str(i),
            att.student.get_full_name(),
            att.get_status_display(),
            att.arrival_time.strftime('%I:%M %p') if att.arrival_time else '—',
            att.notes or '—',
        ])
    t = Table(rows, colWidths=[0.35 * inch, 1.9 * inch, 1.15 * inch, 1.1 * inch, 2.25 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    # ── Summary ────────────────────────────────────────────────────────────
    story += section('Summary')
    story.append(Paragraph(
        f'{counts["present"]} present, {counts["absent"]} absent, {counts["late"]} late, '
        f'{counts["excused"]} excused, {counts["makeup"]} make-up — {attendance_pct}% attendance',
        body,
    ))

    # ── Signature line ─────────────────────────────────────────────────────
    story.append(Spacer(1, 40))
    story.append(Paragraph('Instructor signature: _________________________________  Date: ______________', body))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf.getvalue()
