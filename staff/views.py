import io
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from courses.models import Course, CourseAnnouncement, CourseEnrollment
from documents.models import StudentDocument
from instructor.models import AttendanceRecord, InstructorCourseAssignment, StudentAttendance
from schedule.forms import CalendarEventForm
from schedule.models import CalendarEvent
from students.forms import StudentLoginForm
from students.emails import (
    _send, send_document_review_notification, send_invitation_email,
    send_payment_receipt, send_staff_invitation_email,
)
from students.models import (
    Announcement, CognitiveExamRecord, CourseCompletionRecord,
    CourseReportRecord, EntranceRequirementRecord,
    PatientContactRecord, PaymentHistory, PaymentRecord, PsychomotorSkillRecord,
    ReminderLog, Student, StudentNote,
)
from students.reminders import BalanceDueRule, RegistrationIncompleteRule
from .forms import (
    CognitiveExamForm,
    CourseCompletionForm,
    CourseForm,
    CourseReportForm,
    DocumentReviewForm,
    EditInvitationEmailForm,
    EditStudentInvitationForm,
    EntranceRequirementForm,
    InvitationForm,
    PatientContactForm,
    PaymentHistoryForm,
    PsychomotorSkillForm,
    ReminderBulkSendForm,
    StaffAccountInviteForm,
    StaffAnnouncementForm,
    StaffAssignCourseForm,
    StaffPaymentRecordForm,
    StudentNoteForm,
    StaffInviteAcceptForm,
    StaffStudentEditForm,
)
from .mixins import staff_required
from .models import StaffInvitation, StudentInvitation


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

def _attendance_summary(student, course):
    """Attendance percentage for a student in their course, with a 172 NAC warning level.

    Green >90%, yellow 80-90%, red <80% — 172 NAC Chapter 13 allows dismissal
    of students who miss more than 20% of class sessions.
    """
    if not course:
        return None
    total_sessions = AttendanceRecord.objects.filter(course=course).count()
    if not total_sessions:
        return None
    present_count = StudentAttendance.objects.filter(
        session__course=course, student=student, status='present',
    ).count()
    pct = round(present_count / total_sessions * 100)
    if pct < 80:
        level = 'red'
    elif pct < 90:
        level = 'yellow'
    else:
        level = 'green'
    return {'pct': pct, 'level': level}


@staff_required
def staff_dashboard(request):
    students = Student.objects.filter(role=Student.Role.STUDENT).select_related('payment').order_by('-date_joined')

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
            'payment':    getattr(s, 'payment', None),
            'attendance': _attendance_summary(s, enrollment.course if enrollment else None),
        })

    # NREMT pass-rate alerts: courses with any rate below 75%
    pass_rate_alerts = []
    for course in Course.objects.all():
        records = CourseCompletionRecord.objects.filter(course=course)
        if not records.exists():
            continue
        cog_taken = records.exclude(nremt_cognitive_result__in=['not_taken', '']).count()
        cog_rate  = round(records.filter(nremt_cognitive_result='pass').count() / cog_taken * 100, 1) if cog_taken else None
        psy_taken = records.exclude(nremt_psychomotor_result__in=['not_taken', '']).count()
        psy_rate  = round(records.filter(nremt_psychomotor_result='pass').count() / psy_taken * 100, 1) if psy_taken else None
        if (cog_rate is not None and cog_rate < 75) or (psy_rate is not None and psy_rate < 75):
            pass_rate_alerts.append({'course': course, 'cog_rate': cog_rate, 'psy_rate': psy_rate})

    # Course evaluation pending counts
    from evaluations.models import CourseEvaluation
    ce_pending_mid = CourseEvaluation.objects.filter(
        eval_type=CourseEvaluation.EvalType.MID_COURSE, status=CourseEvaluation.Status.PENDING
    ).count()
    ce_pending_end = CourseEvaluation.objects.filter(
        eval_type=CourseEvaluation.EvalType.END_COURSE, status=CourseEvaluation.Status.PENDING
    ).count()

    # Semi-annual meeting compliance widget
    from instructor.models import InstructorMeeting
    today = timezone.now().date()
    instructors = Student.objects.filter(role=Student.Role.INSTRUCTOR)
    meeting_compliance = []
    for inst in instructors:
        last_meeting = InstructorMeeting.objects.filter(instructor=inst).order_by('-meeting_date').first()
        if last_meeting:
            days_since = (today - last_meeting.meeting_date).days
            if days_since > 180:
                status = 'overdue'
            elif days_since > 150:
                status = 'due_soon'
            else:
                status = 'ok'
        else:
            status = 'overdue'
        if status in ('overdue', 'due_soon'):
            meeting_compliance.append({
                'instructor':   inst,
                'last_meeting': last_meeting,
                'status':       status,
            })

    # Student invitation status counts
    invite_completed_count = StudentInvitation.objects.filter(used=True).count()
    invite_pending_count   = StudentInvitation.objects.filter(used=False, expires_at__gt=timezone.now()).count()
    invite_expired_count   = StudentInvitation.objects.filter(used=False, expires_at__lte=timezone.now()).count()

    # Department report deadline warnings (172 NAC 13-004(D))
    report_records = CourseReportRecord.objects.filter(
        report_submitted_to_department=False
    ).select_related('course')
    overdue_reports = [r for r in report_records if r.is_overdue]
    soon_reports    = [r for r in report_records if not r.is_overdue and r.deadline_soon]

    return render(request, 'staff/dashboard.html', {
        'rows': rows,
        'pass_rate_alerts': pass_rate_alerts,
        'ce_pending_mid': ce_pending_mid,
        'ce_pending_end': ce_pending_end,
        'meeting_compliance': meeting_compliance,
        'invite_completed_count': invite_completed_count,
        'invite_pending_count':   invite_pending_count,
        'invite_expired_count':   invite_expired_count,
        'overdue_reports': overdue_reports,
        'soon_reports':    soon_reports,
    })


# ── Student detail ────────────────────────────────────────────────────────────

@staff_required
def student_detail(request, pk):
    from decimal import Decimal
    student    = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    enrollment = CourseEnrollment.objects.filter(student=student).first()
    docs       = StudentDocument.objects.filter(student=student).select_related('doc_type').order_by('doc_type__order')
    payment, _ = PaymentRecord.objects.get_or_create(student=student)
    payment_form = StaffPaymentRecordForm(instance=payment)
    history    = student.payment_history.select_related('recorded_by').all()

    doc_forms = [(doc, DocumentReviewForm(initial={'status': doc.status, 'notes': doc.notes})) for doc in docs]
    expiring_docs = [d for d in docs if d.doc_type.required and d.expiration_warning]

    total_paid  = sum(p.amount for p in history)
    total_owed  = enrollment.total_tuition if enrollment else Decimal('0')
    balance_due = max(Decimal('0'), total_owed - total_paid)

    add_payment_form = PaymentHistoryForm()
    notes            = StudentNote.objects.filter(student=student).select_related('created_by')
    note_form        = StudentNoteForm()

    # ── 172 NAC Compliance records ────────────────────────────────────────────
    course = enrollment.course if enrollment else None

    cognitive_exams    = CognitiveExamRecord.objects.filter(student=student).select_related('course')
    psychomotor_skills = PsychomotorSkillRecord.objects.filter(student=student).select_related('course')
    patient_contacts   = PatientContactRecord.objects.filter(student=student).select_related('course')

    # Ensure default entrance requirements exist for this student/course combo
    if course:
        _ensure_entrance_requirements(student, course)
    entrance_reqs = EntranceRequirementRecord.objects.filter(student=student).select_related('course')

    completion_rec, _ = (
        CourseCompletionRecord.objects.get_or_create(student=student, course=course)
        if course else (None, False)
    )

    # Patient contact totals
    pc_totals = {
        'total':                patient_contacts.count(),
        'iv_attempted':         patient_contacts.filter(iv_start_attempted=True).count(),
        'iv_successful':        patient_contacts.filter(iv_start_successful=True).count(),
        'airway_attempted':     patient_contacts.filter(airway_placement_attempted=True).count(),
        'airway_successful':    patient_contacts.filter(airway_placement_successful=True).count(),
    }

    is_aemt = course and course.licensure in ('AEMT', 'PARA') if course else False
    attendance = _attendance_summary(student, course)

    # Course evaluations for this student
    from evaluations.models import CourseEvaluation
    course_evals = CourseEvaluation.objects.filter(student=student).select_related('course')
    mid_eval = course_evals.filter(eval_type='mid', course=course).first() if course else None
    end_eval = course_evals.filter(eval_type='end', course=course).first() if course else None
    eval_type_rows = [
        ('Mid-Course Evaluation',    'mid', mid_eval),
        ('End-of-Course Evaluation', 'end', end_eval),
    ]

    return render(request, 'staff/student_detail.html', {
        'student':            student,
        'enrollment':         enrollment,
        'courses_all':        Course.objects.order_by('option_number'),
        'doc_forms':          doc_forms,
        'expiring_docs':      expiring_docs,
        'payment':            payment,
        'history':            history,
        'total_paid':         total_paid,
        'total_owed':         total_owed,
        'balance_due':        balance_due,
        'add_payment_form':   add_payment_form,
        'payment_form':       payment_form,
        'notes':              notes,
        'note_form':          note_form,
        # Course Evaluations
        'mid_eval':           mid_eval,
        'end_eval':           end_eval,
        'eval_type_rows':     eval_type_rows,
        # Compliance
        'cognitive_exams':    cognitive_exams,
        'psychomotor_skills': psychomotor_skills,
        'patient_contacts':   patient_contacts,
        'entrance_reqs':      entrance_reqs,
        'completion_rec':     completion_rec,
        'pc_totals':          pc_totals,
        'is_aemt':            is_aemt,
        'attendance':         attendance,
        'exam_form':          CognitiveExamForm(),
        'skill_form':         PsychomotorSkillForm(),
        'contact_form':       PatientContactForm(),
        'completion_form':    CourseCompletionForm(instance=completion_rec) if completion_rec else CourseCompletionForm(),
        'active_tab':         request.GET.get('tab', 'overview'),
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


@staff_required
def assign_course(request, pk):
    student    = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    enrollment = CourseEnrollment.objects.filter(student=student).first()
    if request.method == 'POST':
        form = StaffAssignCourseForm(request.POST, instance=enrollment)
        if form.is_valid():
            new_course = form.cleaned_data['course']
            enr = form.save(commit=False)
            enr.student = student
            if not new_course.has_book_option:
                enr.book_included = False
            enr.save()
            book_note = ' with textbook' if enr.book_included else ''
            messages.success(request, f'{student.get_full_name()} assigned to Option {new_course.option_number} — {new_course.name}{book_note}.')
        else:
            messages.error(request, 'Please select a valid course.')
    return redirect('staff_student_detail', pk=pk)


@staff_required
def add_payment(request, pk):
    student = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    if request.method == 'POST':
        form = PaymentHistoryForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.student     = student
            record.recorded_by = request.user
            record.save()
            send_payment_receipt(record)
            messages.success(request, f'Payment of ${record.amount} recorded.')
        else:
            messages.error(request, 'Please correct the errors below.')
    return redirect('staff_student_detail', pk=pk)


@staff_required
def edit_payment_info(request, pk):
    student = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    payment, _ = PaymentRecord.objects.get_or_create(student=student)
    if request.method == 'POST':
        form = StaffPaymentRecordForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            messages.success(request, f'Payment info updated for {student.get_full_name()}.')
        else:
            messages.error(request, 'Please correct the errors below.')
    return redirect('staff_student_detail', pk=pk)


# ── Document download (pre-signed S3 URL or local) ───────────────────────────

@staff_required
def document_download(request, doc_id):
    """Redirect to a pre-signed download URL (5-min expiry on S3, direct URL locally)."""
    doc = get_object_or_404(StudentDocument, pk=doc_id)
    return redirect(doc.file.url)


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
        send_document_review_notification(doc)
        messages.success(request, f'{doc.doc_type.label} marked as {doc.status}.')
    return redirect('staff_student_detail', pk=doc.student_id)


# ── Course management ─────────────────────────────────────────────────────────

@staff_required
def course_list(request):
    from datetime import timedelta
    today   = timezone.now().date()
    soon    = today + timedelta(days=7)
    courses = Course.objects.all().order_by('order', 'option_number')

    rows = []
    for c in courses:
        enrolled = c.enrollments.count()
        if not c.is_active:
            status = 'inactive'
        elif c.registration_close_date and today > c.registration_close_date:
            status = 'closed'
        elif c.max_students and enrolled >= c.max_students:
            status = 'full'
        elif c.registration_close_date and c.registration_close_date <= soon:
            status = 'closing'
        else:
            status = 'open'
        rows.append({'course': c, 'enrolled': enrolled, 'status': status})

    return render(request, 'staff/course_list.html', {'rows': rows})


@staff_required
def course_detail(request, pk):
    from datetime import timedelta
    course = get_object_or_404(Course, pk=pk)

    today = timezone.now().date()
    soon  = today + timedelta(days=7)
    enrolled = course.enrollments.count()
    if not course.is_active:
        status = 'inactive'
    elif course.registration_close_date and today > course.registration_close_date:
        status = 'closed'
    elif course.max_students and enrolled >= course.max_students:
        status = 'full'
    elif course.registration_close_date and course.registration_close_date <= soon:
        status = 'closing'
    else:
        status = 'open'

    enrollments = CourseEnrollment.objects.filter(course=course).select_related('student') \
        .order_by('student__last_name', 'student__first_name')

    all_sessions   = AttendanceRecord.objects.filter(course=course).order_by('-session_date')
    total_sessions = all_sessions.count()

    participant_rows = []
    for enrollment in enrollments:
        student     = enrollment.student
        att_records = StudentAttendance.objects.filter(session__course=course, student=student)
        present_count = att_records.filter(status='present').count()
        absent_count  = att_records.filter(status='absent').count()
        late_count    = att_records.filter(status='late').count()
        excused_count = att_records.filter(status='excused').count()
        pct = round(present_count / total_sessions * 100) if total_sessions else None
        participant_rows.append({
            'enrollment':     enrollment,
            'student':        student,
            'present':        present_count,
            'absent':         absent_count,
            'late':           late_count,
            'excused':        excused_count,
            'pct':            pct,
            'low_attendance': pct is not None and pct < 80,
        })

    instructor_assignments = InstructorCourseAssignment.objects.filter(
        course=course, is_active=True
    ).select_related('instructor')

    reminder_logs = ReminderLog.objects.filter(course=course).select_related('student').order_by('-sent_at')[:15]
    announcements = CourseAnnouncement.objects.filter(course=course).order_by('-created_at')

    return render(request, 'staff/course_detail.html', {
        'course':                course,
        'status':                status,
        'enrolled':              enrolled,
        'participant_rows':      participant_rows,
        'sessions':              all_sessions[:15],
        'total_sessions':        total_sessions,
        'instructor_assignments': instructor_assignments,
        'reminder_logs':         reminder_logs,
        'announcements':         announcements,
    })


@staff_required
def course_add(request):
    form = CourseForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Course created.')
        return redirect('staff_course_list')
    return render(request, 'staff/course_form.html', {'form': form, 'action': 'Add'})


@staff_required
def course_edit(request, pk):
    course = get_object_or_404(Course, pk=pk)
    form   = CourseForm(request.POST or None, instance=course)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Course "{course.name}" updated.')
        return redirect('staff_course_list')
    return render(request, 'staff/course_form.html', {'form': form, 'action': 'Edit', 'course': course})


@staff_required
def course_delete(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action', 'deactivate')
        if action == 'delete':
            name = course.name
            course.delete()
            messages.success(request, f'Course "{name}" deleted.')
        else:
            course.is_active = False
            course.save()
            messages.success(request, f'Course "{course.name}" deactivated.')
    return redirect('staff_course_list')


# ── Invitations ───────────────────────────────────────────────────────────────

@staff_required
def invite_student(request):
    form        = InvitationForm(request.POST or None)
    invitations = StudentInvitation.objects.select_related('created_by', 'course').order_by('-created_at')[:20]

    invite_link = None

    if request.method == 'POST' and form.is_valid():
        email       = form.cleaned_data['email']
        course      = form.cleaned_data['course']
        inv         = StudentInvitation.objects.create(email=email, course=course, created_by=request.user)
        invite_link = request.build_absolute_uri(f'/register/invite/{inv.token}/')
        send_invitation_email(inv, invite_link)
        messages.success(request, f'Invite sent to {email}.')
        form        = InvitationForm()
        invitations = StudentInvitation.objects.select_related('created_by', 'course').order_by('-created_at')[:20]

    courses_active = Course.objects.filter(is_active=True).order_by('option_number')
    return render(request, 'staff/invite.html', {
        'form': form, 'invitations': invitations, 'invite_link': invite_link,
        'courses_active': courses_active,
    })


@staff_required
def resend_student_invite(request, pk):
    inv = get_object_or_404(StudentInvitation, pk=pk)
    if request.method == 'POST':
        if inv.used:
            messages.error(request, 'This invitation has already been used.')
        else:
            inv.expires_at = timezone.now() + timedelta(days=7)
            inv.save(update_fields=['expires_at'])
            invite_link = request.build_absolute_uri(f'/register/invite/{inv.token}/')
            send_invitation_email(inv, invite_link)
            messages.success(request, f'Invite resent to {inv.email}.')
    return redirect('staff_invite')


@staff_required
def edit_student_invite(request, pk):
    inv = get_object_or_404(StudentInvitation, pk=pk)
    if request.method == 'POST':
        if inv.used:
            messages.error(request, 'This invitation has already been used.')
        else:
            form = EditStudentInvitationForm(request.POST)
            if form.is_valid():
                inv.email  = form.cleaned_data['email']
                inv.course = form.cleaned_data['course']
                inv.save(update_fields=['email', 'course'])
                messages.success(request, 'Invitation updated.')
            else:
                first_error = next(iter(form.errors.values()))[0] if form.errors else 'Please correct the errors and try again.'
                messages.error(request, first_error)
    return redirect('staff_invite')


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
        c = enrollment.course
        location_parts = [p for p in [c.location_name, c.location_address, c.location_city, c.location_state] if p]
        rows = [
            ['Course',       f'Option {c.option_number} — {c.name}'],
            ['Licensure',    c.get_licensure_display() if c.licensure else '—'],
            ['Tag',          c.tag],
        ]
        if c.has_book_option:
            rows.append(['Textbook', 'Included' if enrollment.book_included else 'Not included'])
        rows += [
            ['Total Tuition', f'${enrollment.total_tuition:,.0f}'],
            ['Min. Down',    f'${c.min_down:,.0f}'],
            ['Shirt Size',   enrollment.shirt_size or '—'],
            ['Location',     ', '.join(location_parts) if location_parts else '—'],
            ['Start Date',   str(c.start_date) if c.start_date else '—'],
            ['End Date',     str(c.end_date) if c.end_date else '—'],
            ['Schedule',     c.schedule_notes or '—'],
            ['Enrolled At',  enrollment.enrolled_at.strftime('%B %d, %Y')],
        ]
        story.append(kv_table(rows))
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
    import base64 as _b64
    from reportlab.platypus import Image as RLImage

    def _sig_element(b64_data, label):
        """Return a signature row: label + image (if base64) or text."""
        rows = []
        if b64_data and b64_data.startswith('data:image/'):
            try:
                _, encoded = b64_data.split(',', 1)
                img_bytes = _b64.b64decode(encoded)
                img_buf   = io.BytesIO(img_bytes)
                sig_img   = RLImage(img_buf, width=2.5*inch, height=0.7*inch)
                rows.append([label, sig_img])
            except Exception:
                rows.append([label, b64_data[:40] + '…' if b64_data else '—'])
        else:
            rows.append([label, b64_data or '—'])
        return rows

    story += section('Signatures')
    sig_data = [
        ['Handbook Signed', ('Yes — ' + student.handbook_signed_at.strftime('%B %d, %Y') if student.handbook_signed and student.handbook_signed_at else ('Yes' if student.handbook_signed else 'No'))],
        ['Contract Signed', ('Yes — ' + student.contract_signed_at.strftime('%B %d, %Y') if student.contract_signed and student.contract_signed_at else ('Yes' if student.contract_signed else 'No'))],
    ]
    sig_data += _sig_element(student.handbook_sig_name, 'Handbook Sig.')
    sig_data += _sig_element(student.contract_sig_name, 'Contract Sig.')
    story.append(kv_table(sig_data))

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


@staff_required
def invoice_pdf(request, pk):
    from decimal import Decimal

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
    history    = student.payment_history.order_by('payment_date')

    total_paid  = sum(p.amount for p in history)
    total_owed  = enrollment.total_tuition if enrollment else Decimal('0')
    balance_due = max(Decimal('0'), total_owed - total_paid)

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
        Paragraph('Invoice', ParagraphStyle('sub', parent=body, textColor=colors.HexColor('#5a7a9a'), fontSize=10)),
        Spacer(1, 10),
    ]

    story += section('Bill To')
    story.append(kv_table([
        ['Name',         student.get_full_name()],
        ['Email',        student.email],
        ['Phone',        student.phone or '—'],
        ['Address',      f'{student.address}, {student.city}, {student.state} {student.zip_code}'.strip(', ')],
        ['Invoice Date', timezone.now().strftime('%B %d, %Y')],
    ]))

    story += section('Course & Tuition')
    if enrollment:
        c = enrollment.course
        rows = [['Course', f'Option {c.option_number} — {c.name}']]
        if c.has_book_option:
            rows.append(['Textbook', 'Included' if enrollment.book_included else 'Not included'])
        rows += [
            ['Total Tuition', f'${enrollment.total_tuition:,.2f}'],
            ['Minimum Down',  f'${c.min_down:,.2f}'],
        ]
        story.append(kv_table(rows))
    else:
        story.append(Paragraph('No course assigned.', body))

    if payment and payment.method:
        story += section('Billing Information')
        rows = [
            ['Payment Method', payment.get_method_display()],
            ['Payment Option', payment.get_pay_option_display() or '—'],
        ]
        if payment.method == 'dept':
            rows += [
                ['Department',         payment.dept_name or '—'],
                ['Department Address', payment.dept_address or '—'],
                ['Department Contact', payment.dept_contact or '—'],
                ['Department Email',   payment.dept_email or '—'],
                ['Department Phone',   payment.dept_phone or '—'],
            ]
        story.append(kv_table(rows))

    story += section('Payments Received')
    if history.exists():
        pay_data = [['Date', 'Method', 'Check #', 'Amount']]
        for p in history:
            pay_data.append([
                p.payment_date.strftime('%m/%d/%Y') if p.payment_date else '—',
                p.get_method_display(),
                p.check_number or '—',
                f'${p.amount:,.2f}',
            ])
        t = Table(pay_data, colWidths=[1.5*inch, 1.75*inch, 1.5*inch, 2*inch])
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
        story.append(Paragraph('No payments recorded.', body))

    story += section('Balance Summary')
    story.append(kv_table([
        ['Total Tuition', f'${total_owed:,.2f}'],
        ['Total Paid',    f'${total_paid:,.2f}'],
        ['Balance Due',   f'${balance_due:,.2f}'],
    ]))

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        'No refunds on PEMSE courses.',
        ParagraphStyle('note', parent=body, textColor=colors.HexColor('#7a5c00'), fontSize=8),
    ))
    story.append(Paragraph(
        f'Generated {timezone.now().strftime("%B %d, %Y %I:%M %p")} — PEMSE Student Portal',
        ParagraphStyle('footer', parent=body, textColor=colors.HexColor('#999999'), fontSize=8),
    ))

    doc.build(story)
    buf.seek(0)

    safe_name = ''.join(c if c.isalnum() or c in '-_ ' else '' for c in student.get_full_name()).strip()
    response  = HttpResponse(buf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="PEMSE-{safe_name}-invoice.pdf"'
    return response


# ── 172 NAC Compliance — helpers ─────────────────────────────────────────────

_DEFAULT_ENTRANCE_REQS = [
    'Government-issued Photo ID / Driver\'s License',
    'CPR Certification Card',
    'Immunization Records',
    'High School Diploma or GED',
    'Background Check Authorization',
]

def _ensure_entrance_requirements(student, course):
    """Auto-create default entrance requirement rows if none exist yet."""
    if not EntranceRequirementRecord.objects.filter(student=student, course=course).exists():
        EntranceRequirementRecord.objects.bulk_create([
            EntranceRequirementRecord(student=student, course=course, requirement_name=name)
            for name in _DEFAULT_ENTRANCE_REQS
        ])


def _detail_redirect(pk, tab):
    return redirect(f'/staff/students/{pk}/?tab={tab}')


# ── Cognitive Exams ───────────────────────────────────────────────────────────

@staff_required
def add_cognitive_exam(request, pk):
    student    = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    enrollment = CourseEnrollment.objects.filter(student=student).first()
    if request.method == 'POST':
        form = CognitiveExamForm(request.POST)
        if form.is_valid():
            rec             = form.save(commit=False)
            rec.student     = student
            rec.course      = enrollment.course if enrollment else None
            rec.recorded_by = request.user
            rec.save()
            messages.success(request, f'Exam "{rec.exam_name}" recorded.')
        else:
            messages.error(request, 'Please correct the errors in the exam form.')
    return _detail_redirect(pk, 'exams')


@staff_required
def delete_cognitive_exam(request, pk, exam_pk):
    exam = get_object_or_404(CognitiveExamRecord, pk=exam_pk, student_id=pk)
    if request.method == 'POST':
        exam.delete()
        messages.success(request, 'Exam record deleted.')
    return _detail_redirect(pk, 'exams')


# ── Student Notes ─────────────────────────────────────────────────────────────

@staff_required
def add_student_note(request, pk):
    student = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    if request.method == 'POST':
        form = StudentNoteForm(request.POST)
        if form.is_valid():
            note             = form.save(commit=False)
            note.student     = student
            note.created_by  = request.user
            note.save()
            messages.success(request, 'Note added.')
        else:
            messages.error(request, 'Please correct the errors in the note form.')
    return _detail_redirect(pk, 'notes')


@staff_required
def delete_student_note(request, pk, note_pk):
    note = get_object_or_404(StudentNote, pk=note_pk, student_id=pk)
    if request.method == 'POST':
        note.delete()
        messages.success(request, 'Note deleted.')
    return _detail_redirect(pk, 'notes')


# ── Psychomotor Skills ────────────────────────────────────────────────────────

@staff_required
def add_psychomotor_skill(request, pk):
    student    = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    enrollment = CourseEnrollment.objects.filter(student=student).first()
    if request.method == 'POST':
        form = PsychomotorSkillForm(request.POST)
        if form.is_valid():
            rec             = form.save(commit=False)
            rec.student     = student
            rec.course      = enrollment.course if enrollment else None
            rec.recorded_by = request.user
            rec.save()
            messages.success(request, f'Skill "{rec.skill_name}" recorded.')
        else:
            messages.error(request, 'Please correct the errors in the skill form.')
    return _detail_redirect(pk, 'skills')


@staff_required
def delete_psychomotor_skill(request, pk, skill_pk):
    skill = get_object_or_404(PsychomotorSkillRecord, pk=skill_pk, student_id=pk)
    if request.method == 'POST':
        skill.delete()
        messages.success(request, 'Skill record deleted.')
    return _detail_redirect(pk, 'skills')


# ── Patient Contacts ──────────────────────────────────────────────────────────

@staff_required
def add_patient_contact(request, pk):
    student    = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    enrollment = CourseEnrollment.objects.filter(student=student).first()
    if request.method == 'POST':
        form = PatientContactForm(request.POST)
        if form.is_valid():
            rec         = form.save(commit=False)
            rec.student = student
            rec.course  = enrollment.course if enrollment else None
            rec.save()
            messages.success(request, 'Patient contact recorded.')
        else:
            messages.error(request, 'Please correct the errors in the contact form.')
    return _detail_redirect(pk, 'contacts')


@staff_required
def delete_patient_contact(request, pk, contact_pk):
    contact = get_object_or_404(PatientContactRecord, pk=contact_pk, student_id=pk)
    if request.method == 'POST':
        contact.delete()
        messages.success(request, 'Patient contact deleted.')
    return _detail_redirect(pk, 'contacts')


# ── Entrance Requirements ─────────────────────────────────────────────────────

@staff_required
def save_entrance_requirements(request, pk):
    student    = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    enrollment = CourseEnrollment.objects.filter(student=student).first()
    if request.method == 'POST' and enrollment:
        _ensure_entrance_requirements(student, enrollment.course)
        reqs = EntranceRequirementRecord.objects.filter(student=student, course=enrollment.course)
        for req in reqs:
            prefix  = f'req_{req.pk}_'
            req.verified         = request.POST.get(prefix + 'verified') == 'on'
            req.document_on_file = request.POST.get(prefix + 'document_on_file') == 'on'
            req.verified_date    = request.POST.get(prefix + 'verified_date') or None
            req.notes            = request.POST.get(prefix + 'notes', '')
            if req.verified:
                req.verified_by = request.user
            req.save()
        # Allow adding a custom requirement
        custom_name = request.POST.get('new_req_name', '').strip()
        if custom_name:
            EntranceRequirementRecord.objects.create(
                student=student, course=enrollment.course,
                requirement_name=custom_name,
            )
        messages.success(request, 'Entrance requirements updated.')
    return _detail_redirect(pk, 'entrance')


# ── Course Completion ─────────────────────────────────────────────────────────

@staff_required
def save_completion_record(request, pk):
    student    = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    enrollment = CourseEnrollment.objects.filter(student=student).first()
    if request.method == 'POST' and enrollment:
        rec, _ = CourseCompletionRecord.objects.get_or_create(
            student=student, course=enrollment.course
        )
        form = CourseCompletionForm(request.POST, instance=rec)
        if form.is_valid():
            form.save()
            messages.success(request, 'Completion record saved.')
        else:
            messages.error(request, 'Please check the completion form fields.')
    return _detail_redirect(pk, 'completion')


@staff_required
def verification_pdf(request, pk):
    """Per 172 NAC 13-004(A) — Official verification of course completion."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    student    = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    enrollment = CourseEnrollment.objects.filter(student=student).first()
    rec        = CourseCompletionRecord.objects.filter(student=student).first()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=inch, rightMargin=inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
    )

    styles  = getSampleStyleSheet()
    navy    = colors.HexColor('#1a2e4a')
    blue    = colors.HexColor('#2B5EA7')
    lt_gray = colors.HexColor('#f3f6fb')

    center = ParagraphStyle('center', parent=styles['Normal'], alignment=1, fontSize=10)
    h1     = ParagraphStyle('h1', parent=styles['Heading1'], textColor=blue, fontSize=18, spaceAfter=4, alignment=1)
    h2     = ParagraphStyle('h2', parent=styles['Heading2'], textColor=navy, fontSize=11, spaceBefore=14, spaceAfter=4)
    body   = ParagraphStyle('body', parent=styles['Normal'], fontSize=10, leading=14)
    small  = ParagraphStyle('small', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#6b7280'))

    course = enrollment.course if enrollment else None
    is_aemt = course and course.licensure in ('AEMT', 'PARA') if course else False

    story = [
        Paragraph('PANHANDLE EMS EDUCATION', h1),
        Paragraph('Official Verification of Course Completion', ParagraphStyle('sub', parent=center, textColor=blue, fontSize=12)),
        Paragraph('172 NAC Chapter 13-004(A)', ParagraphStyle('reg', parent=center, textColor=colors.HexColor('#9ca3af'), fontSize=9)),
        Spacer(1, 14),
        HRFlowable(width='100%', thickness=2, color=blue),
        Spacer(1, 14),
    ]

    def kv(label, value):
        return Table(
            [[label, value]],
            colWidths=[2.2*inch, 4.3*inch],
            style=TableStyle([
                ('FONTNAME',   (0, 0), (0, 0), 'Helvetica-Bold'),
                ('FONTSIZE',   (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('BACKGROUND', (0, 0), (0, 0), lt_gray),
                ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#dde4ef')),
            ]),
        )

    story += [
        Paragraph('Training Agency', h2),
        kv('Agency Name',     'Panhandle EMS Education'),
        kv('Agency Location', course.location_display if course and course.location_display else 'Scottsbluff, NE'),
        Spacer(1, 8),
        Paragraph('Student Information', h2),
        kv('Student Full Name', student.get_full_name()),
        kv('Course Completed',  course.name if course else '—'),
        kv('Completion Date',   rec.completion_date.strftime('%B %d, %Y') if rec and rec.completion_date else '—'),
        kv('Total Hours',       str(rec.total_hours) if rec else '—'),
    ]

    if is_aemt and rec:
        story += [
            kv('Didactic Hours',         str(rec.didactic_hours)),
            kv('Clinical Hours',         str(rec.clinical_hours)),
            kv('Field Internship Hours', str(rec.field_internship_hours)),
        ]

    story += [Spacer(1, 14)]

    story += [
        Paragraph('Official Attestation', h2),
        Paragraph(
            f'This is to certify that the above-named student has successfully completed the '
            f'<b>{course.name if course else "EMS"}</b> course offered by Panhandle EMS Education '
            f'in accordance with Nebraska Department of Health and Human Services regulations '
            f'(172 NAC Chapter 13).',
            body,
        ),
        Spacer(1, 28),
    ]

    sig_name  = rec.verified_by_name  if rec and rec.verified_by_name  else '___________________________'
    sig_title = rec.verified_by_title if rec and rec.verified_by_title else '___________________________'
    sig_date  = rec.verification_date.strftime('%B %d, %Y') if rec and rec.verification_date else '___________________________'

    story.append(Table(
        [
            ['Signature:', '___________________________', 'Date:', sig_date],
            ['Printed Name:', sig_name, 'Title:', sig_title],
        ],
        colWidths=[1.1*inch, 2.8*inch, 0.6*inch, 2*inch],
        style=TableStyle([
            ('FONTNAME',   (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME',   (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW',  (1, 0), (1, 0), 0.5, colors.black),
            ('LINEBELOW',  (1, 1), (1, 1), 0.5, colors.black),
            ('LINEBELOW',  (3, 0), (3, 0), 0.5, colors.black),
            ('LINEBELOW',  (3, 1), (3, 1), 0.5, colors.black),
        ]),
    ))

    story += [
        Spacer(1, 24),
        HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#d1d5db')),
        Spacer(1, 6),
        Paragraph(
            f'Generated {timezone.now().strftime("%B %d, %Y")} — Panhandle EMS Education — '
            f'This document constitutes official verification per 172 NAC 13-004(A).',
            small,
        ),
    ]

    doc.build(story)
    buf.seek(0)
    safe = ''.join(c if c.isalnum() or c in '-_ ' else '' for c in student.get_full_name()).strip()
    resp = HttpResponse(buf, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="PEMSE-{safe}-verification.pdf"'
    return resp


# ── Course Reports ────────────────────────────────────────────────────────────

@staff_required
def course_reports(request):
    from datetime import timedelta
    today   = timezone.now().date()
    courses = Course.objects.all().order_by('order', 'option_number')

    rows = []
    for c in courses:
        report   = getattr(c, 'department_report', None)
        deadline = None
        if c.end_date:
            deadline = c.end_date + timedelta(days=30)
        overdue = (
            not (report and report.report_submitted_to_department)
            and deadline
            and today > deadline
        )
        soon = (
            not (report and report.report_submitted_to_department)
            and deadline
            and today >= deadline - timedelta(days=7)
            and not overdue
        )
        rows.append({
            'course':   c,
            'report':   report,
            'deadline': deadline,
            'overdue':  overdue,
            'soon':     soon,
        })

    return render(request, 'staff/course_reports.html', {'rows': rows, 'today': today})


@staff_required
def course_report_detail(request, course_pk):
    from datetime import timedelta
    course  = get_object_or_404(Course, pk=course_pk)
    report, _ = CourseReportRecord.objects.get_or_create(
        course=course,
        defaults={
            'course_location':  course.location_display or '',
            'submission_deadline': (course.end_date + timedelta(days=30)) if course.end_date else None,
        },
    )
    form = CourseReportForm(request.POST or None, instance=report)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Course report saved.')
        return redirect('staff_course_reports')
    return render(request, 'staff/course_report_form.html', {
        'form':   form,
        'course': course,
        'report': report,
    })


@staff_required
def department_report_pdf(request, course_pk):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    course  = get_object_or_404(Course, pk=course_pk)
    report  = getattr(course, 'department_report', None)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=inch, rightMargin=inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
    )

    styles = getSampleStyleSheet()
    navy   = colors.HexColor('#1a2e4a')
    blue   = colors.HexColor('#2B5EA7')
    lt     = colors.HexColor('#f3f6fb')

    h1   = ParagraphStyle('h1', parent=styles['Heading1'], textColor=blue, fontSize=16, spaceAfter=4, alignment=1)
    h2   = ParagraphStyle('h2', parent=styles['Heading2'], textColor=navy, fontSize=11, spaceBefore=12, spaceAfter=4)
    body = styles['Normal']
    body.fontSize = 10
    small = ParagraphStyle('small', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#6b7280'))

    is_aemt = course.licensure in ('AEMT', 'PARA')

    def kv(label, value):
        return Table(
            [[label, str(value) if value is not None else '—']],
            colWidths=[2.5*inch, 4*inch],
            style=TableStyle([
                ('FONTNAME',      (0, 0), (0, 0), 'Helvetica-Bold'),
                ('FONTSIZE',      (0, 0), (-1, -1), 10),
                ('TOPPADDING',    (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('BACKGROUND',    (0, 0), (0, 0), lt),
                ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#dde4ef')),
            ]),
        )

    story = [
        Paragraph('PANHANDLE EMS EDUCATION', h1),
        Paragraph('Course Completion Report — Nebraska DHHS', ParagraphStyle('sub', parent=styles['Normal'], alignment=1, fontSize=11, textColor=blue)),
        Paragraph('172 NAC Chapter 13-004(D)', ParagraphStyle('reg', parent=styles['Normal'], alignment=1, fontSize=9, textColor=colors.HexColor('#9ca3af'))),
        Spacer(1, 12),
        HRFlowable(width='100%', thickness=2, color=blue),
        Spacer(1, 12),
        Paragraph('Course Information', h2),
        kv('Training Agency',    report.training_agency_name if report else 'Panhandle EMS Education'),
        kv('Course Location',    report.course_location if report else course.location_display or '—'),
        kv('Course Name',        course.name),
        kv('Instructor(s)',      report.instructor_names if report else '—'),
        kv('Course Start Date',  str(course.start_date) if course.start_date else '—'),
        kv('Course End Date',    str(course.end_date) if course.end_date else '—'),
        Spacer(1, 8),
        Paragraph('Enrollment Statistics', h2),
        kv('Students Enrolled',  report.students_enrolled if report else '—'),
        kv('Students Withdrew',  report.students_withdrew if report else '—'),
        kv('Students Completed', report.students_completed if report else '—'),
        kv('Pass Rate',          f"{report.pass_rate}%" if report and report.pass_rate is not None else '—'),
        Spacer(1, 8),
        Paragraph('Hours', h2),
        kv('Total Didactic Hours', report.total_didactic_hours if report else '—'),
    ]

    if is_aemt and report:
        story += [
            kv('Total Clinical Hours',        report.total_clinical_hours),
            kv('Total Field Internship Hours', report.total_field_hours),
        ]

    story += [
        Spacer(1, 8),
        Paragraph('Submission Status', h2),
        kv('Submitted to DHHS',    'Yes' if report and report.report_submitted_to_department else 'No'),
        kv('Submission Date',      str(report.report_submitted_date) if report and report.report_submitted_date else '—'),
        kv('Submission Deadline',  str(report.submission_deadline) if report and report.submission_deadline else '—'),
        Spacer(1, 20),
        HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#d1d5db')),
        Spacer(1, 6),
        Paragraph(
            f'Generated {timezone.now().strftime("%B %d, %Y")} — Panhandle EMS Education — '
            f'172 NAC Chapter 13-004(D) Department Report',
            small,
        ),
    ]

    doc.build(story)
    buf.seek(0)
    safe = ''.join(c if c.isalnum() or c in '-_ ' else '' for c in course.name).strip()
    resp = HttpResponse(buf, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="PEMSE-dept-report-{safe}.pdf"'
    return resp


# ── NREMT Pass Rates ──────────────────────────────────────────────────────────

@staff_required
def pass_rates(request):
    """Per-course NREMT first-attempt pass rate tracker (75% minimum threshold)."""
    courses = Course.objects.order_by('order', 'option_number')

    course_data = []
    for course in courses:
        records = CourseCompletionRecord.objects.filter(course=course)
        if not records.exists():
            continue

        total = records.count()

        # Cognitive: exclude not-taken / blank; count pass
        cog_taken = records.exclude(
            nremt_cognitive_result__in=['not_taken', '']
        ).count()
        cog_pass = records.filter(nremt_cognitive_result='pass').count()
        cog_rate = round(cog_pass / cog_taken * 100, 1) if cog_taken else None

        # Psychomotor
        psy_taken = records.exclude(
            nremt_psychomotor_result__in=['not_taken', '']
        ).count()
        psy_pass = records.filter(nremt_psychomotor_result='pass').count()
        psy_rate = round(psy_pass / psy_taken * 100, 1) if psy_taken else None

        below_75 = (
            (cog_rate is not None and cog_rate < 75) or
            (psy_rate is not None and psy_rate < 75)
        )

        course_data.append({
            'course':    course,
            'total':     total,
            'cog_taken': cog_taken,
            'cog_pass':  cog_pass,
            'cog_rate':  cog_rate,
            'psy_taken': psy_taken,
            'psy_pass':  psy_pass,
            'psy_rate':  psy_rate,
            'below_75':  below_75,
        })

    return render(request, 'staff/pass_rates.html', {'course_data': course_data})


# ── Course Evaluations (staff) ────────────────────────────────────────────────

@staff_required
def course_eval_overview(request):
    from evaluations.models import CourseEvaluation
    ce_pending_mid = CourseEvaluation.objects.filter(
        eval_type='mid', status='pending'
    ).count()
    ce_pending_end = CourseEvaluation.objects.filter(
        eval_type='end', status='pending'
    ).count()

    course_summaries = []
    for c in Course.objects.order_by('option_number'):
        evals = CourseEvaluation.objects.filter(course=c)
        if not evals.exists():
            continue
        course_summaries.append({
            'course':        c,
            'mid_pending':   evals.filter(eval_type='mid', status='pending').count(),
            'mid_completed': evals.filter(eval_type='mid', status='completed').count(),
            'end_pending':   evals.filter(eval_type='end', status='pending').count(),
            'end_completed': evals.filter(eval_type='end', status='completed').count(),
            'total':         evals.count(),
        })

    return render(request, 'staff/course_eval_overview.html', {
        'ce_pending_mid':  ce_pending_mid,
        'ce_pending_end':  ce_pending_end,
        'course_summaries': course_summaries,
    })


# ── Reminders ────────────────────────────────────────────────────────────────

@staff_required
def reminder_dashboard(request):
    logs = ReminderLog.objects.select_related('student', 'sent_by', 'course').all()[:100]
    return render(request, 'staff/reminder_dashboard.html', {'logs': logs})


@staff_required
def reminder_bulk_send(request):
    today            = timezone.localdate()
    form             = ReminderBulkSendForm(request.POST or None)
    preview_mode     = False
    sent_count       = None
    matched_students = []
    selected_course  = None
    audience_label   = None
    audience_value   = None
    sent_subject     = None
    sent_body        = None

    AUDIENCE_RULES = {
        'registration_incomplete': RegistrationIncompleteRule(),
        'balance_due':             BalanceDueRule(),
    }

    if request.method == 'POST' and form.is_valid():
        action     = request.POST.get('action', 'preview')
        audience   = form.cleaned_data['audience']
        course     = form.cleaned_data['course']
        subject    = form.cleaned_data['subject']
        body       = form.cleaned_data['body']
        audience_label  = dict(ReminderBulkSendForm.AUDIENCE_CHOICES)[audience]
        audience_value  = audience
        selected_course = course
        sent_subject    = subject
        sent_body       = body

        if audience in AUDIENCE_RULES:
            students = [s for s, _ctx in AUDIENCE_RULES[audience].candidates(today)]
        else:
            students = list(Student.objects.filter(role=Student.Role.STUDENT).exclude(
                enroll_status=Student.EnrollStatus.WITHDRAWN
            ))
        if course:
            students = [s for s in students if getattr(s, 'enrollment', None) and s.enrollment.course_id == course.id]

        if action == 'preview':
            matched_students = students
            preview_mode = True

        elif action == 'confirm':
            student_ids = set(request.POST.getlist('student_ids'))
            sent_count = 0
            for student in students:
                if str(student.pk) not in student_ids:
                    continue
                _send(subject, body, student.email)
                ReminderLog.objects.create(
                    student=student, rule_key=f'manual_{audience}', channel=ReminderLog.Channel.MANUAL,
                    course=course, sent_by=request.user, subject=subject, body=body,
                )
                sent_count += 1
            messages.success(request, f'Reminder sent to {sent_count} student(s).')

    return render(request, 'staff/reminder_send.html', {
        'form':             form,
        'preview_mode':     preview_mode,
        'matched_students': matched_students,
        'selected_course':  selected_course,
        'audience_label':   audience_label,
        'audience_value':   audience_value,
        'sent_subject':     sent_subject,
        'sent_body':        sent_body,
        'sent_count':       sent_count,
    })


@staff_required
def backup_list(request):
    try:
        _dirs, files = default_storage.listdir('backups')
    except FileNotFoundError:
        files = []
    backups = []
    for name in sorted(files, reverse=True)[:100]:
        full_name = f'backups/{name}'
        backups.append({
            'name':     name,
            'size':     default_storage.size(full_name),
            'modified': default_storage.get_modified_time(full_name),
            'url':      default_storage.url(full_name),
        })
    return render(request, 'staff/backup_list.html', {'backups': backups})


@staff_required
def course_eval_send(request):
    from evaluations.models import CourseEvaluation
    courses       = Course.objects.filter(is_active=True).order_by('option_number')
    preview_mode  = False
    eval_links    = []
    created_count = 0
    students_in_course = []
    selected_course    = None
    selected_type      = None

    if request.method == 'POST':
        action    = request.POST.get('action', 'preview')
        course_id = request.POST.get('course')
        eval_type = request.POST.get('eval_type', 'mid')

        if course_id:
            selected_course = Course.objects.filter(pk=course_id).first()

        if action == 'preview' and selected_course:
            enrollments = CourseEnrollment.objects.filter(
                course=selected_course
            ).select_related('student')
            for e in enrollments:
                already = CourseEvaluation.objects.filter(
                    student=e.student, course=selected_course, eval_type=eval_type
                ).exists()
                students_in_course.append({'student': e.student, 'already_sent': already})
            selected_type = eval_type
            preview_mode  = True

        elif action == 'confirm' and selected_course:
            student_ids   = request.POST.getlist('student_ids')
            eval_type_val = request.POST.get('eval_type', 'mid')
            for sid in student_ids:
                try:
                    st = Student.objects.get(pk=sid, role=Student.Role.STUDENT)
                    obj, created = CourseEvaluation.objects.get_or_create(
                        student=st, course=selected_course, eval_type=eval_type_val,
                        defaults={'created_by': request.user},
                    )
                    if created:
                        created_count += 1
                    link = request.build_absolute_uri(f'/evaluations/course/{obj.token}/')
                    eval_links.append({'student': st, 'eval': obj, 'link': link})
                except Student.DoesNotExist:
                    pass
            selected_type = eval_type_val
            if created_count:
                messages.success(request, f'{created_count} evaluation(s) created.')

    return render(request, 'staff/course_eval_send.html', {
        'courses':            courses,
        'students_in_course': students_in_course,
        'selected_course':    selected_course,
        'selected_type':      selected_type,
        'preview_mode':       preview_mode,
        'eval_links':         eval_links,
        'created_count':      created_count,
        'eval_types':         [('mid', 'Mid-Course Evaluation'), ('end', 'End-of-Course Evaluation')],
    })


@staff_required
def course_eval_detail(request, pk):
    from evaluations.models import CourseEvaluation
    eval_obj = get_object_or_404(CourseEvaluation, pk=pk)
    return render(request, 'staff/course_eval_detail.html', {'eval': eval_obj})


@staff_required
def course_eval_results(request, course_pk):
    from evaluations.models import CourseEvaluation
    course    = get_object_or_404(Course, pk=course_pk)
    completed = list(CourseEvaluation.objects.filter(course=course, status='completed'))
    total_sent = CourseEvaluation.objects.filter(course=course).count()

    SECTIONS = [
        ('Course Content & Curriculum', [
            ('content_objectives_clear',       'Learning objectives were clear'),
            ('content_material_relevant',      'Material was relevant to EMS practice'),
            ('content_material_current',       'Material was current / up-to-date'),
            ('content_difficulty_appropriate', 'Difficulty level was appropriate'),
            ('content_theory_lab_balance',     'Theory vs. lab time balance was good'),
        ]),
        ('Instruction Quality', [
            ('instruction_knowledge',          'Instructor demonstrated strong knowledge'),
            ('instruction_communication',      'Instructor communicated effectively'),
            ('instruction_feedback',           'Instructor provided helpful feedback'),
            ('instruction_availability',       'Instructor was available and accessible'),
            ('instruction_preparation',        'Instructor was well prepared'),
            ('instruction_respected_students', 'Instructor respected all students'),
        ]),
        ('Facilities & Resources', [
            ('facility_classroom_adequate',  'Classroom space was adequate'),
            ('facility_equipment_adequate',  'Equipment was adequate'),
            ('facility_supplies_adequate',   'Supplies were adequate'),
            ('facility_schedule_reasonable', 'Class schedule was reasonable'),
        ]),
        ('Overall Experience', [
            ('overall_satisfaction',       'Overall satisfaction with the course'),
            ('overall_prepared_for_nremt', 'Course prepared me for NREMT'),
        ]),
    ]

    sections_with_stats = []
    for sec_name, fields in SECTIONS:
        qs = []
        for field, label in fields:
            vals = [getattr(e, field) for e in completed if getattr(e, field) is not None]
            avg  = round(sum(vals) / len(vals), 1) if vals else None
            dist = {i: vals.count(i) for i in range(1, 6)}
            colors_map = {1: '#dc2626', 2: '#f87171', 3: '#d97706', 4: '#10b981', 5: '#059669'}
        max_cnt = max(dist.values()) if dist and max(dist.values()) > 0 else 1
        bars = [
            {
                'val': i, 'count': dist[i],
                'color': colors_map[i],
                'height': max(2, round(dist[i] / max_cnt * 36)),
            }
            for i in range(1, 6)
        ]
        qs.append({'label': label, 'field': field, 'avg': avg, 'dist': dist, 'bars': bars, 'n': len(vals)})
        sections_with_stats.append({'name': sec_name, 'questions': qs})

    written = {
        'What Worked Well':        [e.what_worked_well for e in completed if e.what_worked_well],
        'What Could Be Improved':  [e.what_could_be_improved for e in completed if e.what_could_be_improved],
        'Suggestions for Future':  [e.suggestions_for_future for e in completed if e.suggestions_for_future],
        'Additional Comments':     [e.additional_comments for e in completed if e.additional_comments],
    }

    overall_scores = [e.average_score for e in completed if e.average_score is not None]
    overall_avg = round(sum(overall_scores) / len(overall_scores), 1) if overall_scores else None

    return render(request, 'staff/course_eval_results.html', {
        'course':       course,
        'completed':    completed,
        'total_sent':   total_sent,
        'sections':     sections_with_stats,
        'written':      written,
        'overall_avg':  overall_avg,
    })


@staff_required
def course_eval_results_csv(request, course_pk):
    import csv as _csv
    from evaluations.models import CourseEvaluation
    course    = get_object_or_404(Course, pk=course_pk)
    completed = CourseEvaluation.objects.filter(course=course, status='completed').select_related('student')

    resp = HttpResponse(content_type='text/csv')
    safe = ''.join(c if c.isalnum() or c in '-_' else '' for c in course.name)
    resp['Content-Disposition'] = f'attachment; filename="PEMSE-{safe}-evals.csv"'

    w = _csv.writer(resp)
    headers = [
        'Student', 'Eval Type', 'Completed At',
        'content_objectives_clear', 'content_material_relevant', 'content_material_current',
        'content_difficulty_appropriate', 'content_theory_lab_balance',
        'instruction_knowledge', 'instruction_communication', 'instruction_feedback',
        'instruction_availability', 'instruction_preparation', 'instruction_respected_students',
        'facility_classroom_adequate', 'facility_equipment_adequate',
        'facility_supplies_adequate', 'facility_schedule_reasonable',
        'overall_satisfaction', 'overall_prepared_for_nremt', 'average_score',
        'what_worked_well', 'what_could_be_improved', 'suggestions_for_future', 'additional_comments',
    ]
    w.writerow(headers)
    for e in completed:
        w.writerow([
            e.student.get_full_name(), e.get_eval_type_display(),
            e.completed_at.strftime('%Y-%m-%d %H:%M') if e.completed_at else '',
            e.content_objectives_clear, e.content_material_relevant, e.content_material_current,
            e.content_difficulty_appropriate, e.content_theory_lab_balance,
            e.instruction_knowledge, e.instruction_communication, e.instruction_feedback,
            e.instruction_availability, e.instruction_preparation, e.instruction_respected_students,
            e.facility_classroom_adequate, e.facility_equipment_adequate,
            e.facility_supplies_adequate, e.facility_schedule_reasonable,
            e.overall_satisfaction, e.overall_prepared_for_nremt, e.average_score,
            e.what_worked_well, e.what_could_be_improved, e.suggestions_for_future, e.additional_comments,
        ])
    return resp


@staff_required
def course_eval_results_pdf(request, course_pk):
    from evaluations.models import CourseEvaluation
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    course    = get_object_or_404(Course, pk=course_pk)
    completed = list(CourseEvaluation.objects.filter(course=course, status='completed'))
    total_sent = CourseEvaluation.objects.filter(course=course).count()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch,  bottomMargin=0.75*inch,
    )
    styles = getSampleStyleSheet()
    navy   = colors.HexColor('#1a2e4a')
    blue   = colors.HexColor('#2B5EA7')
    lt     = colors.HexColor('#f3f6fb')
    h1   = ParagraphStyle('h1', parent=styles['Heading1'], textColor=blue, fontSize=16, spaceAfter=2, alignment=1)
    h2   = ParagraphStyle('h2', parent=styles['Heading2'], textColor=navy, fontSize=11, spaceBefore=14, spaceAfter=4)
    body = ParagraphStyle('body', parent=styles['Normal'], fontSize=9, leading=13)
    small = ParagraphStyle('small', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#6b7280'))

    overall_scores = [e.average_score for e in completed if e.average_score is not None]
    overall_avg    = round(sum(overall_scores) / len(overall_scores), 1) if overall_scores else None

    story = [
        Paragraph('PANHANDLE EMS EDUCATION', h1),
        Paragraph('Course Evaluation Results', ParagraphStyle('sub', parent=body, alignment=1, fontSize=11, textColor=blue)),
        Spacer(1, 8),
        HRFlowable(width='100%', thickness=2, color=blue),
        Spacer(1, 8),
        Paragraph(f'Course: {course.name}', h2),
        Paragraph(
            f'Responses: {len(completed)} of {total_sent} students   |   '
            f'Response rate: {round(len(completed)/total_sent*100)}%   |   '
            f'Overall average: {overall_avg if overall_avg else "—"}/5.0',
            body,
        ),
        Spacer(1, 10),
    ]

    SECTIONS = [
        ('Course Content & Curriculum', [
            ('content_objectives_clear', 'Objectives were clear'),
            ('content_material_relevant', 'Material was relevant'),
            ('content_material_current', 'Material was current'),
            ('content_difficulty_appropriate', 'Difficulty was appropriate'),
            ('content_theory_lab_balance', 'Theory/lab balance was good'),
        ]),
        ('Instruction Quality', [
            ('instruction_knowledge', 'Instructor knowledge'),
            ('instruction_communication', 'Instructor communication'),
            ('instruction_feedback', 'Helpful feedback provided'),
            ('instruction_availability', 'Instructor availability'),
            ('instruction_preparation', 'Instructor preparation'),
            ('instruction_respected_students', 'Students were respected'),
        ]),
        ('Facilities & Resources', [
            ('facility_classroom_adequate', 'Classroom space'),
            ('facility_equipment_adequate', 'Equipment'),
            ('facility_supplies_adequate', 'Supplies'),
            ('facility_schedule_reasonable', 'Schedule'),
        ]),
        ('Overall Experience', [
            ('overall_satisfaction', 'Overall satisfaction'),
            ('overall_prepared_for_nremt', 'Prepared for NREMT'),
        ]),
    ]

    ts = TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), colors.HexColor('#dde4ef')),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#dde4ef')),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, lt]),
    ])

    for sec_name, fields in SECTIONS:
        story.append(Paragraph(sec_name, h2))
        rows = [['Question', 'Avg', 'n', '1', '2', '3', '4', '5']]
        for field, label in fields:
            vals = [getattr(e, field) for e in completed if getattr(e, field) is not None]
            avg  = round(sum(vals) / len(vals), 1) if vals else '—'
            rows.append([label, str(avg), str(len(vals))] + [str(vals.count(i)) for i in range(1, 6)])
        story.append(Table(rows, colWidths=[2.8*inch, 0.5*inch, 0.4*inch] + [0.45*inch]*5, style=ts))

    # Written feedback
    WRITTEN = [
        ('what_worked_well', 'What Worked Well'),
        ('what_could_be_improved', 'What Could Be Improved'),
        ('suggestions_for_future', 'Suggestions for Future Courses'),
        ('additional_comments', 'Additional Comments'),
    ]
    for field, label in WRITTEN:
        items = [getattr(e, field) for e in completed if getattr(e, field)]
        if items:
            story.append(Paragraph(label, h2))
            for item in items:
                story.append(Paragraph(f'• {item}', body))
                story.append(Spacer(1, 3))

    story += [
        Spacer(1, 16),
        HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#d1d5db')),
        Spacer(1, 4),
        Paragraph(f'Generated {timezone.now().strftime("%B %d, %Y")} — Panhandle EMS Education', small),
    ]

    doc.build(story)
    buf.seek(0)
    safe = ''.join(c if c.isalnum() or c in '-_' else '' for c in course.name)
    resp = HttpResponse(buf, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="PEMSE-{safe}-eval-results.pdf"'
    return resp


# ── Instructor Management ─────────────────────────────────────────────────────

@staff_required
def staff_instructor_list(request):
    from datetime import timedelta
    from instructor.models import InstructorMeeting
    today = timezone.now().date()
    instructors = Student.objects.filter(role=Student.Role.INSTRUCTOR).order_by('last_name', 'first_name')

    rows = []
    for inst in instructors:
        assignments = inst.course_assignments.filter(is_active=True).select_related('course')
        last_obs    = inst.observations.order_by('-observation_date').first()
        last_meeting = InstructorMeeting.objects.filter(instructor=inst).order_by('-meeting_date').first()

        # Semi-annual meeting status
        meeting_status = 'overdue'
        if last_meeting:
            months_since = (today - last_meeting.meeting_date).days / 30
            if months_since <= 5:
                meeting_status = 'ok'
            elif months_since <= 6:
                meeting_status = 'due_soon'

        # License status
        license_status = 'ok'
        if inst.instructor_license_expiry:
            days_left = (inst.instructor_license_expiry - today).days
            if days_left < 0:
                license_status = 'expired'
            elif days_left <= 90:
                license_status = 'expiring'

        from decimal import Decimal
        from django.db.models import Sum
        hours_year = inst.hour_logs.filter(
            session_date__gte=today.replace(month=1, day=1)
        ).aggregate(t=Sum('hours'))['t'] or Decimal('0')

        rows.append({
            'instructor':     inst,
            'assignments':    assignments,
            'last_obs':       last_obs,
            'last_meeting':   last_meeting,
            'meeting_status': meeting_status,
            'license_status': license_status,
            'hours_year':     hours_year,
        })

    return render(request, 'staff/instructor_list.html', {'rows': rows})


@staff_required
def staff_instructor_add(request):
    from .forms import InstructorCreateForm
    form = InstructorCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        instructor = form.save()
        messages.success(request, f'Instructor account created for {instructor.get_full_name()}.')
        return redirect('staff_instructor_detail', pk=instructor.pk)
    return render(request, 'staff/instructor_add.html', {'form': form})


@staff_required
def staff_instructor_detail(request, pk):
    from datetime import timedelta
    from django.db.models import Sum
    from decimal import Decimal
    from instructor.models import (
        InstructorCourseAssignment, InstructionalHourLog,
        InstructorObservation, InstructorMeeting, RemediationPlan,
    )

    instructor  = get_object_or_404(Student, pk=pk, role=Student.Role.INSTRUCTOR)
    assignments = InstructorCourseAssignment.objects.filter(
        instructor=instructor
    ).select_related('course', 'assigned_by').order_by('-assigned_at')
    hour_logs   = InstructionalHourLog.objects.filter(
        instructor=instructor
    ).select_related('course', 'verified_by').order_by('-session_date')
    observations  = InstructorObservation.objects.filter(instructor=instructor).order_by('-observation_date')
    meetings      = InstructorMeeting.objects.filter(instructor=instructor).order_by('-meeting_date')
    rem_plans     = RemediationPlan.objects.filter(instructor=instructor).order_by('-created_date')

    hours_total = hour_logs.aggregate(t=Sum('hours'))['t'] or Decimal('0')

    active_tab = request.GET.get('tab', 'profile')
    tab_list = [
        ('profile',      'Profile'),
        ('courses',      'Course Assignments'),
        ('hours',        'Hour Logs'),
        ('observations', 'Observations'),
        ('meetings',     'Meetings'),
        ('remediation',  'Remediation Plans'),
    ]

    return render(request, 'staff/instructor_detail.html', {
        'instructor':   instructor,
        'assignments':  assignments,
        'hour_logs':    hour_logs,
        'observations': observations,
        'meetings':     meetings,
        'rem_plans':    rem_plans,
        'hours_total':  hours_total,
        'active_tab':   active_tab,
        'tab_list':     tab_list,
    })


@staff_required
def staff_instructor_assign_course(request, pk):
    from .forms import InstructorCourseAssignmentForm
    instructor = get_object_or_404(Student, pk=pk, role=Student.Role.INSTRUCTOR)
    form = InstructorCourseAssignmentForm(request.POST or None, instructor=instructor)
    if request.method == 'POST' and form.is_valid():
        assignment             = form.save(commit=False)
        assignment.instructor  = instructor
        assignment.assigned_by = request.user
        assignment.save()
        messages.success(request, f'{instructor.get_full_name()} assigned to {assignment.course}.')
        return redirect('staff_instructor_detail', pk=pk)
    return render(request, 'staff/instructor_assign_course.html', {
        'form': form, 'instructor': instructor,
    })


@staff_required
def staff_instructor_verify_hours(request, pk):
    from instructor.models import InstructionalHourLog
    instructor = get_object_or_404(Student, pk=pk, role=Student.Role.INSTRUCTOR)
    if request.method == 'POST':
        ids = request.POST.getlist('hour_ids')
        updated = InstructionalHourLog.objects.filter(
            pk__in=ids, instructor=instructor, verified=False
        ).update(verified=True, verified_by=request.user, verified_at=timezone.now())
        messages.success(request, f'{updated} hour log(s) verified.')
    return redirect('staff_instructor_detail', pk=pk)


@staff_required
def staff_instructor_observe(request, pk):
    from .forms import InstructorObservationForm
    instructor = get_object_or_404(Student, pk=pk, role=Student.Role.INSTRUCTOR)
    form = InstructorObservationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obs             = form.save(commit=False)
        obs.instructor  = instructor
        obs.observed_by = request.user
        obs.save()
        messages.success(request, 'Observation recorded.')
        return redirect('staff_instructor_detail', pk=f'{pk}?tab=observations')
    return render(request, 'staff/instructor_observe.html', {
        'form': form, 'instructor': instructor,
    })


@staff_required
def staff_instructor_meeting(request, pk):
    from .forms import InstructorMeetingForm
    instructor = get_object_or_404(Student, pk=pk, role=Student.Role.INSTRUCTOR)
    form = InstructorMeetingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        meeting              = form.save(commit=False)
        meeting.instructor   = instructor
        meeting.conducted_by = request.user
        meeting.save()
        messages.success(request, 'Meeting record saved.')
        return redirect('staff_instructor_detail', pk=f'{pk}?tab=meetings')
    return render(request, 'staff/instructor_meeting.html', {
        'form': form, 'instructor': instructor,
    })


@staff_required
def staff_instructor_remediation(request, pk):
    from .forms import RemediationPlanForm
    from datetime import timedelta
    instructor = get_object_or_404(Student, pk=pk, role=Student.Role.INSTRUCTOR)
    form = RemediationPlanForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        plan            = form.save(commit=False)
        plan.instructor = instructor
        plan.created_by = request.user
        # Default retain_until to 5 years from today per 172 NAC Chapter 13
        if not plan.retain_until:
            plan.retain_until = timezone.now().date() + timedelta(days=5*365)
        plan.save()
        messages.success(request, 'Remediation plan created.')
        return redirect('staff_instructor_detail', pk=f'{pk}?tab=remediation')
    return render(request, 'staff/instructor_remediation.html', {
        'form': form, 'instructor': instructor,
    })


# ── Staff Account Management ────────────────────────────────────────────────

@staff_required
def staff_account_list(request):
    accounts = Student.objects.filter(
        role__in=[Student.Role.STAFF, Student.Role.ADMIN]
    ).order_by('last_name', 'first_name')
    return render(request, 'staff/staff_account_list.html', {'accounts': accounts})


@staff_required
def staff_account_invite(request):
    form        = StaffAccountInviteForm(request.POST or None)
    invitations = StaffInvitation.objects.select_related('created_by').order_by('-created_at')[:20]

    invite_link = None

    if request.method == 'POST' and form.is_valid():
        email       = form.cleaned_data['email']
        inv         = StaffInvitation.objects.create(email=email, created_by=request.user)
        invite_link = request.build_absolute_uri(f'/staff/accounts/invite/{inv.token}/')
        send_staff_invitation_email(inv, invite_link)
        messages.success(request, f'Invite sent to {email}.')
        form        = StaffAccountInviteForm()
        invitations = StaffInvitation.objects.select_related('created_by').order_by('-created_at')[:20]

    return render(request, 'staff/staff_account_invite.html', {
        'form': form, 'invitations': invitations, 'invite_link': invite_link,
    })


@staff_required
def resend_staff_invite(request, pk):
    inv = get_object_or_404(StaffInvitation, pk=pk)
    if request.method == 'POST':
        if inv.used:
            messages.error(request, 'This invitation has already been used.')
        else:
            inv.expires_at = timezone.now() + timedelta(days=7)
            inv.save(update_fields=['expires_at'])
            invite_link = request.build_absolute_uri(f'/staff/accounts/invite/{inv.token}/')
            send_staff_invitation_email(inv, invite_link)
            messages.success(request, f'Invite resent to {inv.email}.')
    return redirect('staff_account_invite')


@staff_required
def edit_staff_invite(request, pk):
    inv = get_object_or_404(StaffInvitation, pk=pk)
    if request.method == 'POST':
        if inv.used:
            messages.error(request, 'This invitation has already been used.')
        else:
            form = EditInvitationEmailForm(request.POST)
            if form.is_valid():
                inv.email = form.cleaned_data['email']
                inv.save(update_fields=['email'])
                messages.success(request, 'Invitation email updated.')
            else:
                messages.error(request, form.errors['email'][0] if form.errors.get('email') else 'Please enter a valid email.')
    return redirect('staff_account_invite')


def staff_invite_accept(request, token):
    """Account setup view for an invited office staff member — no login required."""
    try:
        invitation = StaffInvitation.objects.get(token=token)
    except StaffInvitation.DoesNotExist:
        messages.error(request, 'This invitation link is invalid.')
        return redirect('staff_login')

    if not invitation.is_valid:
        messages.error(request, 'This invitation link has expired or has already been used.')
        return redirect('staff_login')

    if request.user.is_authenticated:
        return redirect('staff_dashboard')

    if Student.objects.filter(email__iexact=invitation.email).exists():
        messages.error(request, 'An account with this email already exists.')
        return redirect('staff_login')

    form = StaffInviteAcceptForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        staff           = form.save(commit=False)
        staff.username  = invitation.email.lower()
        staff.email     = invitation.email.lower()
        staff.role      = Student.Role.STAFF
        staff.set_password(form.cleaned_data['password1'])
        staff.save()
        invitation.used    = True
        invitation.used_at = timezone.now()
        invitation.save()
        login(request, staff, backend='students.backends.EmailBackend')
        messages.success(request, f'Welcome, {staff.first_name}! Your staff account is ready.')
        return redirect('staff_dashboard')

    return render(request, 'staff/staff_invite_accept.html', {'form': form, 'invite_email': invitation.email})


# ── Calendar ──────────────────────────────────────────────────────────────────

@staff_required
def staff_calendar(request):
    events = CalendarEvent.objects.select_related('course').order_by('date', 'start_time')

    course_id = request.GET.get('course')
    if course_id:
        events = events.filter(course_id=course_id)

    today = timezone.now().date()
    events = list(events)
    return render(request, 'staff/calendar.html', {
        'upcoming_events': [e for e in events if e.date >= today],
        'past_events':     [e for e in events if e.date < today],
        'courses':         Course.objects.order_by('option_number'),
        'selected_course': int(course_id) if course_id else None,
        'feed_token':      request.user.calendar_token,
    })


@staff_required
def staff_calendar_add(request):
    form = CalendarEventForm(Course.objects.order_by('option_number'), request.POST or None)
    if request.method == 'POST' and form.is_valid():
        event            = form.save(commit=False)
        event.created_by = request.user
        event.save()
        messages.success(request, f'Added "{event.title}" to the calendar.')
        return redirect('staff_calendar')
    return render(request, 'staff/calendar_form.html', {'form': form})


@staff_required
def staff_calendar_edit(request, pk):
    event = get_object_or_404(CalendarEvent, pk=pk)
    form = CalendarEventForm(Course.objects.order_by('option_number'), request.POST or None, instance=event)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Calendar event updated.')
        return redirect('staff_calendar')
    return render(request, 'staff/calendar_form.html', {'form': form, 'event': event})


@staff_required
def staff_calendar_delete(request, pk):
    event = get_object_or_404(CalendarEvent, pk=pk)
    if request.method == 'POST':
        event.delete()
        messages.success(request, 'Calendar event deleted.')
    return redirect('staff_calendar')
