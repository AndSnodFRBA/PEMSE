import io

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from courses.models import CourseEnrollment
from documents.models import StudentDocument
from students.forms import StudentLoginForm
from students.models import Announcement, Student
from .forms import (
    DocumentReviewForm,
    InvitationForm,
    StaffAnnouncementForm,
    StaffStudentEditForm,
)
from .mixins import staff_required
from .models import StudentInvitation


# ── Auth ──────────────────────────────────────────────────────────────────────

def staff_login_view(request):
    if request.user.is_authenticated:
        if request.user.is_office_staff:
            return redirect('staff_dashboard')
        return redirect('dashboard')

    form = StudentLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        if not user.is_office_staff:
            messages.error(request, 'This login is for office staff only.')
        else:
            login(request, user)
            return redirect('staff_dashboard')

    return render(request, 'staff/login.html', {'form': form})


def staff_logout_view(request):
    logout(request)
    return redirect('staff_login')


# ── Dashboard ─────────────────────────────────────────────────────────────────

@staff_required
def staff_dashboard(request):
    students = (
        Student.objects.filter(role=Student.Role.STUDENT)
        .prefetch_related('studentdocument_set__doc_type', 'courseenrollment')
        .order_by('-date_joined')
    )

    # Attach quick-status data to each student
    rows = []
    for s in students:
        enrollment = CourseEnrollment.objects.filter(student=s).first()
        req_docs   = StudentDocument.objects.filter(student=s, doc_type__required=True)
        rows.append({
            'student':    s,
            'enrollment': enrollment,
            'docs_count': req_docs.count(),
            'docs_ok':    req_docs.filter(status='approved').count() >= 3,
        })

    return render(request, 'staff/dashboard.html', {'rows': rows})


# ── Student detail ────────────────────────────────────────────────────────────

@staff_required
def student_detail(request, pk):
    student    = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    enrollment = CourseEnrollment.objects.filter(student=student).first()
    docs       = StudentDocument.objects.filter(student=student).select_related('doc_type').order_by('doc_type__order')
    payment    = getattr(student, 'payment', None)

    doc_forms = [(doc, DocumentReviewForm(initial={'status': doc.status, 'notes': doc.notes})) for doc in docs]

    return render(request, 'staff/student_detail.html', {
        'student':    student,
        'enrollment': enrollment,
        'doc_forms':  doc_forms,
        'payment':    payment,
    })


@staff_required
def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    form    = StaffStudentEditForm(request.POST or None, instance=student)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{student.get_full_name()} updated.')
        return redirect('staff_student_detail', pk=pk)
    return render(request, 'staff/student_edit.html', {'form': form, 'student': student})


# ── Document review ───────────────────────────────────────────────────────────

@staff_required
def review_document(request, doc_id):
    doc  = get_object_or_404(StudentDocument, pk=doc_id)
    form = DocumentReviewForm(request.POST)
    if request.method == 'POST' and form.is_valid():
        doc.status      = form.cleaned_data['status']
        doc.notes       = form.cleaned_data['notes']
        doc.reviewed_by = request.user
        doc.reviewed_at = timezone.now()
        doc.save()
        messages.success(request, f'{doc.doc_type.label} marked as {doc.status}.')
    return redirect('staff_student_detail', pk=doc.student_id)


# ── Invitations ───────────────────────────────────────────────────────────────

@staff_required
def invite_student(request):
    form        = InvitationForm(request.POST or None)
    invitations = StudentInvitation.objects.select_related('created_by').order_by('-created_at')[:20]

    invite_link = None

    if request.method == 'POST' and form.is_valid():
        email       = form.cleaned_data['email']
        inv         = StudentInvitation.objects.create(email=email, created_by=request.user)
        invite_link = request.build_absolute_uri(f'/register/invite/{inv.token}/')

        try:
            send_mail(
                subject='You\'re invited to enroll at Panhandle EMS Education',
                message=(
                    f'Hello,\n\n'
                    f'You have been invited to create an account at the PEMSE Student Portal.\n\n'
                    f'Click the link below to register (link expires in 7 days):\n{invite_link}\n\n'
                    f'If you were not expecting this invitation, you can ignore this email.\n\n'
                    f'— Panhandle EMS Education\n'
                    f'  309 E 27th St, Scottsbluff NE | 308.631.2424'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            messages.success(request, f'Invitation email sent to {email}.')
        except Exception:
            messages.warning(request, 'Email could not be sent — copy the link below and share it manually.')

        form        = InvitationForm()
        invitations = StudentInvitation.objects.select_related('created_by').order_by('-created_at')[:20]

    return render(request, 'staff/invite.html', {'form': form, 'invitations': invitations, 'invite_link': invite_link})


# ── Announcements ─────────────────────────────────────────────────────────────

@staff_required
def announcement_list(request):
    announcements = Announcement.objects.select_related('created_by').order_by('-created_at')
    return render(request, 'staff/announcements.html', {'announcements': announcements})


@staff_required
def announcement_create(request):
    form = StaffAnnouncementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ann            = form.save(commit=False)
        ann.created_by = request.user
        ann.save()
        messages.success(request, 'Announcement posted.')
        return redirect('staff_announcements')
    return render(request, 'staff/announcement_form.html', {'form': form, 'action': 'New'})


@staff_required
def announcement_edit(request, pk):
    ann  = get_object_or_404(Announcement, pk=pk)
    form = StaffAnnouncementForm(request.POST or None, instance=ann)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Announcement updated.')
        return redirect('staff_announcements')
    return render(request, 'staff/announcement_form.html', {'form': form, 'action': 'Edit', 'ann': ann})


@staff_required
def announcement_delete(request, pk):
    ann = get_object_or_404(Announcement, pk=pk)
    if request.method == 'POST':
        ann.delete()
        messages.success(request, 'Announcement deleted.')
    return redirect('staff_announcements')


# ── PDF ───────────────────────────────────────────────────────────────────────

@staff_required
def student_pdf(request, pk):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    student    = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    enrollment = CourseEnrollment.objects.filter(student=student).first()
    payment    = getattr(student, 'payment', None)
    docs       = StudentDocument.objects.filter(student=student).select_related('doc_type')

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
    )

    styles  = getSampleStyleSheet()
    navy    = colors.HexColor('#2B5EA7')
    lt_gray = colors.HexColor('#f3f6fb')

    h1 = ParagraphStyle('h1', parent=styles['Heading1'], textColor=navy, fontSize=16, spaceAfter=4)
    h2 = ParagraphStyle('h2', parent=styles['Heading2'], textColor=navy, fontSize=11, spaceBefore=12, spaceAfter=4)
    body = styles['Normal']
    body.fontSize = 9

    def section(title):
        return [Paragraph(title, h2), Spacer(1, 4)]

    def kv_table(data):
        t = Table(data, colWidths=[2*inch, 4.75*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), lt_gray),
            ('FONTNAME',   (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 9),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#d1dae8')),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, lt_gray]),
            ('TOPPADDING',  (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ]))
        return t

    story = [
        Paragraph('Panhandle EMS Education', h1),
        Paragraph('Student Registration Form', ParagraphStyle('sub', parent=body, textColor=colors.HexColor('#5a7a9a'), fontSize=10)),
        Spacer(1, 10),
    ]

    # Personal info
    story += section('Personal Information')
    story.append(kv_table([
        ['Full Name',      student.get_full_name()],
        ['Email',          student.email],
        ['Phone',          student.phone or '—'],
        ['Address',        f'{student.address}, {student.city}, {student.state} {student.zip_code}'.strip(', ')],
        ['Date of Birth',  str(student.date_of_birth) if student.date_of_birth else '—'],
        ['OK to Text',     'Yes' if student.ok_to_text else ('No' if student.ok_to_text is False else '—')],
        ['Date Joined',    student.date_joined.strftime('%B %d, %Y')],
    ]))

    # Course
    story += section('Course Enrollment')
    if enrollment:
        story.append(kv_table([
            ['Course',       f'Option {enrollment.course.option_number} — {enrollment.course.name}'],
            ['Tag',          enrollment.course.tag],
            ['Price',        f'${enrollment.course.price:,.0f}'],
            ['Min. Down',    f'${enrollment.course.min_down:,.0f}'],
            ['Shirt Size',   enrollment.shirt_size or '—'],
            ['Enrolled At',  enrollment.enrolled_at.strftime('%B %d, %Y')],
        ]))
    else:
        story.append(Paragraph('No course selected.', body))

    # Payment
    story += section('Payment Information')
    if payment and payment.method:
        rows = [
            ['Method',      payment.get_method_display()],
            ['Option',      payment.get_pay_option_display() or '—'],
        ]
        if payment.method == 'check':
            rows.append(['Check #', payment.check_number or '—'])
        if payment.method == 'dept':
            rows += [
                ['Dept. Name',    payment.dept_name],
                ['Dept. Address', payment.dept_address],
                ['Dept. Contact', payment.dept_contact],
                ['Dept. Email',   payment.dept_email],
                ['Dept. Phone',   payment.dept_phone],
            ]
        story.append(kv_table(rows))
    else:
        story.append(Paragraph('No payment information on file.', body))

    # Enrollment status
    story += section('Enrollment Status')
    story.append(kv_table([
        ['Status',          student.get_enroll_status_display()],
        ['Reg. Submitted',  'Yes — ' + student.reg_submitted_at.strftime('%B %d, %Y %I:%M %p') if student.reg_submitted and student.reg_submitted_at else ('Yes' if student.reg_submitted else 'No')],
        ['Conf. Number',    student.reg_conf_number or '—'],
    ]))

    # Signatures
    story += section('Signatures')
    story.append(kv_table([
        ['Handbook Signed',  ('Yes — ' + student.handbook_signed_at.strftime('%B %d, %Y') if student.handbook_signed and student.handbook_signed_at else ('Yes' if student.handbook_signed else 'No'))],
        ['Handbook Sig.',    student.handbook_sig_name or '—'],
        ['Contract Signed',  ('Yes — ' + student.contract_signed_at.strftime('%B %d, %Y') if student.contract_signed and student.contract_signed_at else ('Yes' if student.contract_signed else 'No'))],
        ['Contract Sig.',    student.contract_sig_name or '—'],
    ]))

    # Documents
    story += section('Uploaded Documents')
    if docs.exists():
        doc_data = [['Document', 'Status', 'Uploaded', 'Notes']]
        for d in docs:
            doc_data.append([
                d.doc_type.label,
                d.get_status_display(),
                d.uploaded_at.strftime('%m/%d/%Y') if d.uploaded_at else '—',
                d.notes or '—',
            ])
        t = Table(doc_data, colWidths=[2*inch, 1*inch, 1.25*inch, 2.5*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0), navy),
            ('TEXTCOLOR',   (0, 0), (-1, 0), colors.white),
            ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, -1), 9),
            ('GRID',        (0, 0), (-1, -1), 0.5, colors.HexColor('#d1dae8')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, lt_gray]),
            ('TOPPADDING',  (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(t)
    else:
        story.append(Paragraph('No documents uploaded.', body))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f'Generated {timezone.now().strftime("%B %d, %Y %I:%M %p")} — PEMSE Student Portal',
        ParagraphStyle('footer', parent=body, textColor=colors.HexColor('#999999'), fontSize=8),
    ))

    doc.build(story)
    buf.seek(0)

    safe_name = ''.join(c if c.isalnum() or c in '-_ ' else '' for c in student.get_full_name()).strip()
    response  = HttpResponse(buf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="PEMSE-{safe_name}-registration.pdf"'
    return response
