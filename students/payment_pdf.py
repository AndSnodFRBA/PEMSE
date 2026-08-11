"""Print-ready payment receipt PDF, generated when staff records a payment."""
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

from .pdf import BORDER, GRAY, LIGHT, NAVY, _footer


def generate_payment_receipt(payment):
    """payment: a students.models.PaymentHistory instance."""
    from students.balance import compute_balance

    student = payment.student
    _, total_paid, total_owed, balance_due = compute_balance(student)
    history = student.payment_history.order_by('payment_date')
    enrollment = None
    from courses.models import CourseEnrollment
    enrollment = CourseEnrollment.objects.filter(student=student).select_related('course').first()

    receipt_number = f'RCPT-{payment.payment_date.year}-{payment.pk:08d}'

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
    thank_you = ParagraphStyle('thank_you', parent=body, textColor=NAVY, fontSize=12, alignment=1, spaceBefore=16)

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
    title_block = [Paragraph('Panhandle EMS Education', h1), Paragraph('Payment Receipt', sub)]
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

    story.append(kv_table([
        ['Receipt #', receipt_number],
        ['Receipt Date', timezone.now().strftime('%B %d, %Y')],
    ]))

    # ── Student info ───────────────────────────────────────────────────────
    story += section('Student')
    story.append(kv_table([
        ['Name', student.get_full_name()],
        ['Email', student.email],
        ['Phone', student.phone or '—'],
        ['Course', f'Option {enrollment.course.option_number} — {enrollment.course.name}' if enrollment else '—'],
    ]))

    # ── This payment ───────────────────────────────────────────────────────
    story += section('Payment Received')
    rows = [
        ['Amount', f'${payment.amount:,.2f}'],
        ['Date', payment.payment_date.strftime('%B %d, %Y')],
        ['Method', payment.get_method_display()],
    ]
    if payment.method == 'check' and payment.check_number:
        rows.append(['Check #', payment.check_number])
    story.append(kv_table(rows))

    # ── Payment history ────────────────────────────────────────────────────
    story += section('Payment History')
    running_paid = Decimal('0')
    hist_rows = [['Date', 'Amount', 'Method', 'Balance']]
    for p in history:
        running_paid += p.amount
        balance = max(Decimal('0'), total_owed - running_paid)
        hist_rows.append([
            p.payment_date.strftime('%m/%d/%Y'),
            f'${p.amount:,.2f}',
            p.get_method_display(),
            f'${balance:,.2f}',
        ])
    hist_table = Table(hist_rows, colWidths=[1.4 * inch, 1.4 * inch, 1.9 * inch, 2.05 * inch])
    hist_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(hist_table)

    story.append(Spacer(1, 8))
    story.append(kv_table([
        ['Total Paid', f'${total_paid:,.2f}'],
        ['Balance Remaining', f'${balance_due:,.2f}'],
    ]))

    story.append(Paragraph('Thank you for your payment!', thank_you))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf.getvalue()
