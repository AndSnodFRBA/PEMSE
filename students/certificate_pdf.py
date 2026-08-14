"""Official course completion certificate — issued once a student's
gradebook meets all completion requirements (172 NAC 13-004(A))."""
import io

from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

PEMSE_NAVY = colors.HexColor('#2B5EA7')
PEMSE_GOLD = colors.HexColor('#C9A84C')


def generate_completion_certificate(student, enrollment, gradebook, completion_record):
    from django.conf import settings
    from students.models import SiteSettings

    site = SiteSettings.get()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    getSampleStyleSheet()

    cert_title = ParagraphStyle('cert_title',
        fontSize=36, textColor=PEMSE_NAVY, alignment=TA_CENTER,
        fontName='Times-Bold', spaceAfter=6)
    cert_subtitle = ParagraphStyle('cert_subtitle',
        fontSize=14, textColor=colors.grey, alignment=TA_CENTER,
        fontName='Times-Italic', spaceAfter=20)
    cert_body = ParagraphStyle('cert_body',
        fontSize=14, textColor=colors.black, alignment=TA_CENTER,
        fontName='Times-Roman', spaceAfter=8)
    cert_name = ParagraphStyle('cert_name',
        fontSize=28, textColor=PEMSE_NAVY, alignment=TA_CENTER,
        fontName='Times-BoldItalic', spaceAfter=8)
    cert_course = ParagraphStyle('cert_course',
        fontSize=18, textColor=PEMSE_NAVY, alignment=TA_CENTER,
        fontName='Times-Bold', spaceAfter=8)
    cert_detail = ParagraphStyle('cert_detail',
        fontSize=11, textColor=colors.darkgrey, alignment=TA_CENTER,
        fontName='Times-Roman', spaceAfter=4)
    cert_small = ParagraphStyle('cert_small',
        fontSize=9, textColor=colors.grey, alignment=TA_CENTER,
        fontName='Times-Roman')

    story = []

    # Decorative top border
    story.append(HRFlowable(width='100%', thickness=4, color=PEMSE_NAVY))
    story.append(HRFlowable(width='100%', thickness=1, color=PEMSE_GOLD, spaceAfter=20))

    # Logo — use the staticfiles finder so this works the same whether
    # running locally or against collectstatic'd files in production.
    logo_path = finders.find('images/PEMSE.jpg')
    if logo_path:
        story.append(Image(logo_path, width=2 * inch, height=1.2 * inch))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph('Certificate of Completion', cert_title))
    story.append(Paragraph(site.agency_name, cert_subtitle))
    story.append(HRFlowable(width='60%', thickness=1, color=PEMSE_GOLD, spaceAfter=16))

    story.append(Paragraph('This certifies that', cert_body))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(student.get_full_name(), cert_name))
    story.append(HRFlowable(width='50%', thickness=1, color=colors.lightgrey, spaceAfter=8))

    story.append(Paragraph('has successfully completed', cert_body))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(enrollment.course.name, cert_course))
    story.append(Spacer(1, 0.05 * inch))

    # Course details
    completion_date = (
        completion_record.completion_date.strftime('%B %d, %Y')
        if completion_record.completion_date else timezone.now().date().strftime('%B %d, %Y')
    )
    story.append(Paragraph(f'Date of Completion: {completion_date}', cert_detail))

    total_hours = completion_record.total_hours or 0
    didactic = completion_record.didactic_hours or 0
    clinical = completion_record.clinical_hours or 0
    field = completion_record.field_internship_hours or 0
    story.append(Paragraph(f'Total Course Hours: {total_hours}', cert_detail))

    if enrollment.course.licensure in ('AEMT', 'PARA'):
        story.append(Paragraph(
            f'Didactic: {didactic} hrs  |  Clinical: {clinical} hrs  |  Field Internship: {field} hrs',
            cert_detail
        ))

    story.append(Spacer(1, 0.2 * inch))
    story.append(HRFlowable(width='60%', thickness=1, color=PEMSE_GOLD, spaceAfter=16))

    # Signature section
    sig_data = [
        ['_______________________________', '_______________________________'],
        [f'{site.agency_director}, {site.agency_director_title}', site.medical_director_name],
        ['NREMT, EMSI; AHA BLS Instructor', site.medical_director_phone],
        [site.agency_name, site.medical_director_title],
    ]
    sig_table = Table(sig_data, colWidths=[3.5 * inch, 3.5 * inch])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, 1), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 1), (-1, 1), PEMSE_NAVY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(sig_table)

    story.append(Spacer(1, 0.15 * inch))
    story.append(HRFlowable(width='100%', thickness=1, color=PEMSE_GOLD, spaceAfter=4))
    story.append(HRFlowable(width='100%', thickness=4, color=PEMSE_NAVY))

    # Footer
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        f'{site.agency_address}  |  {site.agency_email}  |  {site.agency_phone}',
        cert_small
    ))
    story.append(Paragraph(
        f'Per 172 NAC Chapter 13 — Records retained minimum 5 years  |  Issued: {timezone.now().strftime("%B %d, %Y")}',
        cert_small
    ))
    story.append(Paragraph(
        f'Confirmation: {student.reg_conf_number}',
        cert_small
    ))
    story.append(Paragraph(
        f'Generated by {settings.SOFTWARE_COMPANY} — fourlinesoftware.com',
        cert_small
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
