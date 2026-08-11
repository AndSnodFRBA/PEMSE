"""Print-ready PDF of a student's completed registration form.

Shared by the student-facing download and the staff student-detail page, so
the content stays identical regardless of who requests it.
"""
import base64
import io
from decimal import Decimal

from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY   = colors.HexColor('#2B5EA7')
LIGHT  = colors.HexColor('#f3f6fb')
BORDER = colors.HexColor('#d1dae8')
RED    = colors.HexColor('#c0392b')
GRAY   = colors.HexColor('#888888')

CONTRACT_INTRO_TEMPLATE = (
    'I, {name}, agree to the terms and conditions of Panhandle EMS Education, LLC, including '
    '(but not limited to) providing tuition paid in full OR making scheduled payments agreed to '
    'by myself and the Director of PEMSE, prior to the first night of scheduled class.'
)
CONTRACT_PARAGRAPHS = [
    ('Full tuition will be paid prior to FISDAP and final testing. I understand that PEMSE has '
     'the right to and will legally pursue any unpaid tuition under my name.'),
    ('I understand there are no refunds on PEMSE courses. CE hours will NOT be granted on '
     'incomplete courses.'),
]


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(GRAY)
    canvas.drawString(
        0.75 * inch, 0.5 * inch,
        'Panhandle EMS Education — 709 Rosedale Dr., Scottsbluff, NE 69361 — emseducation19@gmail.com',
    )
    canvas.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, f'Page {doc.page}')
    canvas.restoreState()


def generate_registration_pdf(student):
    from courses.models import CourseEnrollment
    from documents.models import DocumentType, StudentDocument

    enrollment = CourseEnrollment.objects.filter(student=student).select_related('course').first()
    payment    = getattr(student, 'payment', None)
    history    = student.payment_history.order_by('payment_date')
    docs_by_type = {
        d.doc_type_id: d for d in StudentDocument.objects.filter(student=student).select_related('doc_type')
    }
    doc_types = DocumentType.objects.all()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.85 * inch,
    )

    styles = getSampleStyleSheet()
    h1  = ParagraphStyle('h1', parent=styles['Heading1'], textColor=NAVY, fontSize=16, spaceAfter=4)
    h2  = ParagraphStyle('h2', parent=styles['Heading2'], textColor=NAVY, fontSize=11, spaceBefore=14, spaceAfter=4)
    sub = ParagraphStyle('sub', parent=styles['Normal'], textColor=colors.HexColor('#5a7a9a'), fontSize=10)
    body = ParagraphStyle('body', parent=styles['Normal'], fontSize=9, leading=13)
    warn = ParagraphStyle('warn', parent=body, textColor=RED, fontName='Helvetica-Bold')
    sig_style = ParagraphStyle(
        'sig', parent=styles['Normal'], fontName='Times-Italic', fontSize=22, textColor=colors.HexColor('#0a2540'),
    )
    small_gray = ParagraphStyle('small_gray', parent=body, textColor=GRAY, fontSize=8)

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
    title_block = [Paragraph('Panhandle EMS Education', h1), Paragraph('Student Registration Form', sub)]
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

    # ── Personal information ──────────────────────────────────────────────
    story += section('Personal Information')
    story.append(kv_table([
        ['Full Name', student.get_full_name()],
        ['Email', student.email],
        ['Phone', student.phone or '—'],
        ['Address', f'{student.address}, {student.city}, {student.state} {student.zip_code}'.strip(', ')],
        ['Date of Birth', str(student.date_of_birth) if student.date_of_birth else '—'],
    ]))

    # ── Course selected ────────────────────────────────────────────────────
    story += section('Course Selected')
    if enrollment:
        c = enrollment.course
        price_line = f'${c.price:,.0f}'
        if c.has_book_option:
            price_line += f' (${c.price_with_book:,.0f} with textbook)'
        story.append(kv_table([
            ['Course', f'Option {c.option_number} — {c.name}'],
            ['Price', price_line],
            ['Minimum Down', f'${c.min_down:,.0f}'],
            ['Total Tuition', f'${enrollment.total_tuition:,.0f}'],
        ]))
    else:
        story.append(Paragraph('No course selected.', body))

    # ── Payment method & schedule ─────────────────────────────────────────
    story += section('Payment Method & Schedule')
    if payment and payment.method:
        rows = [
            ['Method', payment.get_method_display()],
            ['Schedule', payment.get_pay_option_display() or '—'],
        ]
        if payment.method == 'check':
            rows.append(['Check #', payment.check_number or '—'])
        if payment.method == 'dept':
            rows += [
                ['Department', payment.dept_name or '—'],
                ['Dept. Contact', payment.dept_contact or '—'],
                ['Dept. Email', payment.dept_email or '—'],
            ]
        story.append(kv_table(rows))
    else:
        story.append(Paragraph('No payment method on file.', body))

    # ── Payment history with running balance ──────────────────────────────
    story += section('Payment History')
    if history.exists():
        total_owed = enrollment.total_tuition if enrollment else Decimal('0')
        running_paid = Decimal('0')
        rows = [['Date', 'Amount', 'Method', 'Balance']]
        for p in history:
            running_paid += p.amount
            balance = max(Decimal('0'), total_owed - running_paid)
            rows.append([
                p.payment_date.strftime('%m/%d/%Y'),
                f'${p.amount:,.2f}',
                p.get_method_display(),
                f'${balance:,.2f}',
            ])
        story.append(data_table(rows, col_widths=[1.4 * inch, 1.4 * inch, 1.9 * inch, 2.05 * inch]))
    else:
        story.append(Paragraph('No payments recorded yet.', body))

    # ── Handbook ───────────────────────────────────────────────────────────
    story += section('Handbook')
    if student.handbook_signed:
        signed_line = 'Signed'
        if student.handbook_signed_at:
            signed_line += f' {student.handbook_signed_at.strftime("%B %d, %Y")}'
        story.append(Paragraph(signed_line, body))
    else:
        story.append(Paragraph('Not yet signed.', body))

    # ── Document checklist ────────────────────────────────────────────────
    story += section('Document Checklist')
    doc_rows = [['Document', 'Status']]
    for dt in doc_types:
        d = docs_by_type.get(dt.id)
        doc_rows.append([dt.label, d.get_status_display() if d else 'Not uploaded'])
    story.append(data_table(doc_rows, col_widths=[4 * inch, 2.75 * inch]))

    # ── Payment contract text ─────────────────────────────────────────────
    story += section('Payment Contract')
    story.append(Paragraph(CONTRACT_INTRO_TEMPLATE.format(name=student.get_full_name()), body))
    story.append(Spacer(1, 6))
    story.append(Paragraph(CONTRACT_PARAGRAPHS[0], body))
    story.append(Spacer(1, 6))
    story.append(Paragraph(CONTRACT_PARAGRAPHS[1], warn))

    # ── Signature ──────────────────────────────────────────────────────────
    story += section('Signature')
    sig_val = student.contract_sig_name
    if student.contract_signed:
        if sig_val and sig_val.startswith('data:image'):
            try:
                _, encoded = sig_val.split(',', 1)
                img_bytes = base64.b64decode(encoded)
                story.append(RLImage(io.BytesIO(img_bytes), width=2.5 * inch, height=0.7 * inch))
            except Exception:
                story.append(Paragraph('(signature on file)', body))
        elif sig_val:
            story.append(Paragraph(sig_val, sig_style))
        else:
            story.append(Paragraph('(signature on file)', body))
        signed_at = (
            student.contract_signed_at.strftime('%B %d, %Y %I:%M %p')
            if student.contract_signed_at else '—'
        )
        story.append(Paragraph(f'Signed {signed_at}', small_gray))
    else:
        story.append(Paragraph('Not yet signed.', body))

    # ── Confirmation ───────────────────────────────────────────────────────
    story += section('Registration Confirmation')
    submitted_line = (
        student.reg_submitted_at.strftime('%B %d, %Y %I:%M %p')
        if student.reg_submitted_at else ('Yes' if student.reg_submitted else 'Not submitted')
    )
    story.append(kv_table([
        ['Confirmation #', student.reg_conf_number or '—'],
        ['Submitted', submitted_line],
    ]))

    story.append(Spacer(1, 16))
    story.append(Paragraph(f'Generated {timezone.now().strftime("%B %d, %Y %I:%M %p")}', small_gray))
    story.append(Paragraph('Records retained per 172 NAC Chapter 13 — minimum 5 years.', small_gray))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf.getvalue()
