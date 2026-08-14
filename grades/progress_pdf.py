"""Student grade progress report — a snapshot PDF of grades, attendance, and
completion status, for the student's own records (not an official transcript)."""
import io

from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from students.pdf import BORDER, GRAY, LIGHT, NAVY, RED, _footer


def _attendance_summary(student, course):
    from instructor.models import AttendanceRecord, StudentAttendance

    total_sessions = AttendanceRecord.objects.filter(course=course).count()
    if not total_sessions:
        return None
    present_count = StudentAttendance.objects.filter(
        session__course=course, student=student, status='present',
    ).count()
    return {'total': total_sessions, 'present': present_count,
            'pct': round(present_count / total_sessions * 100)}


def generate_progress_report(student, enrollment, gradebook, completion_record, checklist):
    from students.models import SiteSettings

    site = SiteSettings.get()
    course = enrollment.course

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
    small_gray = ParagraphStyle('small_gray', parent=body, textColor=GRAY, fontSize=8)
    grade_big = ParagraphStyle('grade_big', parent=body, fontSize=13, fontName='Helvetica-Bold', textColor=NAVY)

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

    def data_table(rows, col_widths, header=True):
        t = Table(rows, colWidths=col_widths)
        style = [
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]
        if header:
            style += [
                ('BACKGROUND', (0, 0), (-1, 0), NAVY),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
            ]
        t.setStyle(TableStyle(style))
        return t

    story = []

    # ── Header with logo ──────────────────────────────────────────────────
    title_block = [Paragraph(site.agency_name, h1), Paragraph('Student Progress Report', sub)]
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

    # ── Student & course info ──────────────────────────────────────────────
    story += section('Student & Course')
    story.append(kv_table([
        ['Name', student.get_full_name()],
        ['Email', student.email],
        ['Phone', student.phone or '—'],
        ['Course', f'Option {course.option_number} — {course.name}'],
        ['Course Dates', f'{course.start_date.strftime("%b %d, %Y") if course.start_date else "—"} '
                          f'– {course.end_date.strftime("%b %d, %Y") if course.end_date else "—"}'],
        ['Report Generated', timezone.now().strftime('%B %d, %Y')],
    ]))

    # ── Grade summary ──────────────────────────────────────────────────────
    story += section('Grade Summary')
    c1 = gradebook.component_1_average
    se = gradebook.section_exam_average
    fe = gradebook.final_exam_score
    grade_rows = [
        ['Component', 'Weight', 'Score'],
        ['Quizzes, Skills, Worksheets & Participation', '30%',
         f'{c1:.1f}%' if c1 is not None else 'Not yet taken'],
        ['Section Exams', '40%', f'{se:.1f}%' if se is not None else 'Not yet taken'],
        ['Final Exam', '30%', f'{fe:.1f}%' if fe is not None else 'Not yet taken'],
    ]
    overall = gradebook.overall_grade
    overall_display = f'{overall:.1f}%  ({gradebook.letter_grade})' if overall is not None else 'Not yet available'
    grade_table = data_table(grade_rows, col_widths=[3.75 * inch, 1 * inch, 2 * inch])
    story.append(grade_table)
    story.append(Spacer(1, 6))
    story.append(Paragraph(f'OVERALL GRADE: {overall_display}', grade_big))

    # ── Attendance summary ─────────────────────────────────────────────────
    story += section('Attendance Summary')
    attendance = _attendance_summary(student, course)
    if attendance:
        story.append(Paragraph(
            f'Present for {attendance["present"]} of {attendance["total"]} sessions '
            f'({attendance["pct"]}%).',
            body,
        ))
    else:
        story.append(Paragraph('No attendance sessions recorded yet.', body))

    # ── Section exam detail ────────────────────────────────────────────────
    story += section('Section Exam Detail')
    exams = gradebook.section_exam_grades.all()
    if exams:
        exam_rows = [['Exam', 'Score', 'Result']]
        for e in exams:
            name = 'Final Exam' if e.is_final_exam else e.exam_name
            exam_rows.append([name, f'{e.score:.1f}%', 'Pass' if e.is_passing else 'Fail'])
        story.append(data_table(exam_rows, col_widths=[3.75 * inch, 1.5 * inch, 1.5 * inch]))
    else:
        story.append(Paragraph('No exams recorded yet.', body))

    # ── Participation ──────────────────────────────────────────────────────
    story += section('Participation')
    deductions = gradebook.participation_deductions.all()
    story.append(Paragraph(f'Participation score: {gradebook.participation_score}/100', body))
    if deductions:
        story.append(Spacer(1, 4))
        ded_rows = [['Date', 'Reason', 'Points Deducted']]
        for d in deductions:
            ded_rows.append([d.date.strftime('%m/%d/%Y'), d.get_reason_display(), f'-{d.points}'])
        story.append(data_table(ded_rows, col_widths=[1.5 * inch, 4 * inch, 1.25 * inch]))

    # ── Completion requirements checklist ──────────────────────────────────
    story += section('Course Completion Requirements')
    if checklist:
        req_rows = [['Requirement', 'Status', 'Detail']]
        for item in checklist:
            req_rows.append([item['label'], 'Met' if item['met'] else 'Not Met', item['detail']])
        req_table = data_table(req_rows, col_widths=[2.25 * inch, 0.9 * inch, 3.6 * inch])
        story.append(req_table)
    else:
        story.append(Paragraph('Completion tracking not yet available for this course.', body))

    # ── Footer disclaimer ──────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        'This is an unofficial progress report for informational purposes only. '
        'It does not constitute a transcript or certificate of completion.',
        ParagraphStyle('disclaimer', parent=small_gray, textColor=RED),
    ))
    story.append(Paragraph(
        f'Questions about your grades? Contact {site.agency_name} at {site.agency_phone} or {site.agency_email}.',
        small_gray,
    ))
    story.append(Paragraph(
        'This report contains confidential student education records protected under FERPA. '
        'Do not share without authorization.',
        small_gray,
    ))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf.getvalue()
