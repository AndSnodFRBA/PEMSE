import io
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
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
    CourseReportRecord, EntranceRequirementRecord, LatePaymentFee,
    PatientContactRecord, PaymentHistory, PaymentRecord, PsychomotorSkillRecord,
    ReminderLog, Student, StudentNote, StudentNotification,
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
    LatePaymentFeeForm,
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
    WaiveLateFeeForm,
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


def _last_seen_display(student):
    if not student.last_login:
        return 'Never'
    days = (timezone.now() - student.last_login).days
    if days <= 0:
        return 'Today'
    if days == 1:
        return '1 day ago'
    return f'{days} days ago'


def _not_logged_in_7plus(student):
    if not student.last_login:
        return True
    return (timezone.now() - student.last_login).days >= 7


def _student_row(student, enrollment, course):
    """One row of the by-course student table: docs, balance, attendance."""
    from documents.models import DocumentType
    from students.balance import compute_balance

    docs_total    = DocumentType.objects.count()
    docs_uploaded = StudentDocument.objects.filter(student=student).count()
    _, total_paid, total_owed, balance_due = compute_balance(student)

    return {
        'student':      student,
        'enrollment':   enrollment,
        'payment':      getattr(student, 'payment', None),
        'docs_uploaded': docs_uploaded,
        'docs_total':   docs_total,
        'balance_due':  balance_due,
        'attendance':   _attendance_summary(student, course),
        'last_seen':    _last_seen_display(student),
    }


def _passes_filters(student, status_filter=None, search=None, docs_filter=None, login_filter=None):
    if status_filter and student.enroll_status != status_filter:
        return False
    if search:
        q = search.lower()
        haystack = [student.first_name, student.last_name, student.email, student.phone]
        if not any(q in (field or '').lower() for field in haystack):
            return False
    if docs_filter == 'incomplete':
        approved_required = StudentDocument.objects.filter(
            student=student, doc_type__required=True, status='approved',
        ).count()
        if approved_required >= 3:
            return False
    if login_filter == 'stale' and not _not_logged_in_7plus(student):
        return False
    return True


def _course_group(course, status_filter=None, search=None, docs_filter=None, balance_filter=None, login_filter=None):
    enrollments = CourseEnrollment.objects.filter(course=course).select_related('student').order_by(
        'student__last_name', 'student__first_name'
    )
    rows = []
    for enrollment in enrollments:
        student = enrollment.student
        if not _passes_filters(student, status_filter, search, docs_filter, login_filter):
            continue
        row = _student_row(student, enrollment, course)
        if balance_filter == 'outstanding' and not row['balance_due']:
            continue
        rows.append(row)
    return {'course': course, 'rows': rows, 'count': len(rows)}


@staff_required
def staff_dashboard(request):
    from django.db.models import Q
    from students.balance import compute_balance

    today = timezone.now().date()

    show_archived  = request.GET.get('archived') == '1'
    course_filter  = request.GET.get('course') or ''
    status_filter  = request.GET.get('status') or ''
    search         = request.GET.get('q', '').strip()
    docs_filter    = request.GET.get('docs', '')
    balance_filter = request.GET.get('balance', '')
    login_filter   = request.GET.get('login', '')
    any_filter_active = bool(course_filter or status_filter or search or docs_filter or balance_filter or login_filter)

    # A course is "archived" once it's been explicitly deactivated, or its
    # end date has passed — either way it drops out of the active roster.
    archived_q = Q(is_active=False) | (Q(end_date__isnull=False) & Q(end_date__lt=today))
    active_courses_qs   = Course.objects.exclude(archived_q).order_by('option_number')
    archived_courses_qs = Course.objects.filter(archived_q).order_by('option_number')

    if course_filter:
        active_courses_qs   = active_courses_qs.filter(option_number=course_filter)
        archived_courses_qs = archived_courses_qs.filter(option_number=course_filter)

    active_groups = []
    unassigned_rows = []
    if not show_archived:
        for course in active_courses_qs:
            group = _course_group(course, status_filter, search, docs_filter, balance_filter, login_filter)
            if any_filter_active and not group['count']:
                continue
            active_groups.append(group)

        unassigned_qs = Student.objects.filter(
            role=Student.Role.STUDENT, enrollment__isnull=True
        ).order_by('last_name', 'first_name')
        for s in unassigned_qs:
            if not _passes_filters(s, status_filter, search, docs_filter, login_filter):
                continue
            row = _student_row(s, None, None)
            if balance_filter == 'outstanding' and not row['balance_due']:
                continue
            unassigned_rows.append(row)

    archived_groups = []
    if show_archived:
        for course in archived_courses_qs:
            group = _course_group(course, status_filter, search, docs_filter, balance_filter, login_filter)
            if any_filter_active and not group['count']:
                continue
            enrolled_count  = CourseEnrollment.objects.filter(course=course).count()
            completed_count = CourseEnrollment.objects.filter(
                course=course, student__enroll_status=Student.EnrollStatus.COMPLETE
            ).count()
            withdrew_count  = CourseEnrollment.objects.filter(
                course=course, student__enroll_status=Student.EnrollStatus.WITHDRAWN
            ).count()
            group.update({
                'enrolled_count':  enrolled_count,
                'completed_count': completed_count,
                'withdrew_count':  withdrew_count,
                'pass_rate': round(completed_count / enrolled_count * 100, 1) if enrolled_count else None,
            })
            archived_groups.append(group)

    # Student summary widget: active students by course, incomplete enrollments, balances due
    course_breakdown = []
    for course in Course.objects.filter(is_active=True).order_by('option_number'):
        cnt = CourseEnrollment.objects.filter(
            course=course, student__enroll_status=Student.EnrollStatus.ACTIVE
        ).count()
        if cnt:
            course_breakdown.append({'course': course, 'count': cnt})
    total_active_students = sum(c['count'] for c in course_breakdown)
    active_courses_count = len(course_breakdown)

    all_students = Student.objects.filter(role=Student.Role.STUDENT)
    incomplete_enrollment_count = sum(1 for s in all_students if not s.enrollment_complete)
    outstanding_balance_count   = sum(1 for s in all_students if compute_balance(s)[3] > 0)
    pending_docs_count = StudentDocument.objects.filter(status='pending').count()
    nremt_stats = _nremt_overall_stats()

    capacity_warnings = [
        c for c in Course.objects.filter(is_active=True).order_by('option_number')
        if c.capacity_warning or c.is_full
    ]

    # Results count for the current tab (respects all active filters)
    if show_archived:
        students_shown = sum(g['count'] for g in archived_groups)
    else:
        students_shown = sum(g['count'] for g in active_groups) + len(unassigned_rows)
    students_total = all_students.count()

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

    # Instructor license expiry warnings (expired or expiring within 90 days)
    license_warnings = []
    for inst in instructors.filter(instructor_license_expiry__isnull=False):
        days_left = (inst.instructor_license_expiry - today).days
        if days_left < 0:
            license_warnings.append({'instructor': inst, 'status': 'expired', 'days_left': days_left})
        elif days_left <= 90:
            license_warnings.append({'instructor': inst, 'status': 'expiring', 'days_left': days_left})
    license_warnings.sort(key=lambda w: w['days_left'])

    # Student invitation status counts
    invite_completed_count = StudentInvitation.objects.filter(used=True).count()
    invite_pending_count   = StudentInvitation.objects.filter(used=False, expires_at__gt=timezone.now()).count()
    invite_expired_count   = StudentInvitation.objects.filter(used=False, expires_at__lte=timezone.now()).count()

    # Records retention review warnings (172 NAC 13-004(F)(iii))
    retention_flagged = CourseCompletionRecord.objects.filter(
        records_flagged_for_review=True
    ).select_related('student', 'course')

    # At-risk students (overall_grade/is_finalized are Python properties, not
    # DB fields, so filter candidates in Python rather than via queryset).
    from grades.models import GradeBook
    at_risk_students = []
    candidates = GradeBook.objects.filter(
        course__is_active=True, is_finalized=False,
    ).select_related('student', 'course')
    for gb in candidates:
        reasons = []
        if gb.needs_intervention:
            reasons.append(f'Overall grade below 75% ({gb.overall_grade}%)')
        failed_exam = gb.section_exam_grades.filter(is_final_exam=False, score__lt=75).first()
        if failed_exam:
            reasons.append(f'Failed section exam: {failed_exam.exam_name}')
        if gb.participation_score < 75:
            reasons.append('Participation below 75%')
        if reasons:
            at_risk_students.append({'gradebook': gb, 'reasons': reasons})

    # Department report deadline warnings (172 NAC 13-004(D))
    report_records = CourseReportRecord.objects.filter(
        report_submitted_to_department=False
    ).select_related('course')
    overdue_reports = [r for r in report_records if r.is_overdue]
    soon_reports    = [r for r in report_records if not r.is_overdue and r.deadline_soon]

    from students.models import WebhookLog
    last_webhook_run = WebhookLog.objects.first()
    webhook_status = 'none'
    if last_webhook_run:
        days_ago = (timezone.now() - last_webhook_run.triggered_at).days
        if days_ago == 0:
            webhook_status = 'green'
        elif days_ago == 1:
            webhook_status = 'yellow'
        else:
            webhook_status = 'red'

    return render(request, 'staff/dashboard.html', {
        'active_groups':   active_groups,
        'archived_groups': archived_groups,
        'unassigned_rows': unassigned_rows,
        'show_archived':   show_archived,
        'course_filter':   course_filter,
        'status_filter':   status_filter,
        'search':          search,
        'docs_filter':     docs_filter,
        'balance_filter':  balance_filter,
        'login_filter':    login_filter,
        'any_filter_active': any_filter_active,
        'students_shown':   students_shown,
        'students_total':   students_total,
        'enroll_status_choices': Student.EnrollStatus.choices,
        'all_courses':           Course.objects.order_by('option_number'),
        'course_breakdown':      course_breakdown,
        'total_active_students': total_active_students,
        'active_courses_count': active_courses_count,
        'incomplete_enrollment_count': incomplete_enrollment_count,
        'outstanding_balance_count':   outstanding_balance_count,
        'pending_docs_count':          pending_docs_count,
        'capacity_warnings':           capacity_warnings,
        'nremt_stats':                 nremt_stats,
        'pass_rate_alerts': pass_rate_alerts,
        'ce_pending_mid': ce_pending_mid,
        'ce_pending_end': ce_pending_end,
        'meeting_compliance': meeting_compliance,
        'license_warnings': license_warnings,
        'retention_flagged': retention_flagged,
        'at_risk_students': at_risk_students,
        'invite_completed_count': invite_completed_count,
        'invite_pending_count':   invite_pending_count,
        'invite_expired_count':   invite_expired_count,
        'overdue_reports': overdue_reports,
        'soon_reports':    soon_reports,
        'last_webhook_run': last_webhook_run,
        'webhook_status':   webhook_status,
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
    pending_docs_exist = docs.filter(status='pending').exists()

    from django.db.models import Sum
    from students.balance import compute_balance
    _, total_paid, total_owed, balance_due = compute_balance(student)
    tuition_owed = enrollment.total_tuition if enrollment else Decimal('0')
    late_fees = LatePaymentFee.objects.filter(student=student).order_by('-date_applied')
    late_fee_total = late_fees.filter(waived=False).aggregate(
        total=Sum('amount'))['total'] or Decimal('0')

    add_payment_form   = PaymentHistoryForm()
    late_fee_form       = LatePaymentFeeForm()
    waive_late_fee_form = WaiveLateFeeForm()
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

    attendance_sessions = []
    if course:
        recent_sessions = AttendanceRecord.objects.filter(course=course).order_by('-session_date')[:15]
        student_statuses = {
            sa.session_id: sa for sa in
            StudentAttendance.objects.filter(student=student, session__course=course)
        }
        for sess in recent_sessions:
            sa = student_statuses.get(sess.id)
            attendance_sessions.append({
                'session': sess,
                'status_display': sa.get_status_display() if sa else 'Not recorded',
            })

    # Course evaluations for this student
    from evaluations.models import CourseEvaluation
    course_evals = CourseEvaluation.objects.filter(student=student).select_related('course')
    mid_eval = course_evals.filter(eval_type='mid', course=course).first() if course else None
    end_eval = course_evals.filter(eval_type='end', course=course).first() if course else None
    eval_type_rows = [
        ('Mid-Course Evaluation',    'mid', mid_eval),
        ('End-of-Course Evaluation', 'end', end_eval),
    ]

    from grades.models import GradeBook
    gb = GradeBook.objects.filter(student=student, course=enrollment.course).first() if enrollment else None

    certificate_available = False
    if enrollment and gb and completion_rec:
        from grades.views import certificate_requirements_checklist
        _, certificate_available = certificate_requirements_checklist(student, enrollment, gb, completion_rec)

    return render(request, 'staff/student_detail.html', {
        'student':            student,
        'enrollment':         enrollment,
        'gb':                 gb,
        'certificate_available': certificate_available,
        'courses_all':        Course.objects.order_by('option_number'),
        'doc_forms':          doc_forms,
        'pending_docs_exist': pending_docs_exist,
        'expiring_docs':      expiring_docs,
        'payment':            payment,
        'history':            history,
        'total_paid':         total_paid,
        'total_owed':         total_owed,
        'balance_due':        balance_due,
        'tuition_owed':       tuition_owed,
        'late_fees':          late_fees,
        'late_fee_total':     late_fee_total,
        'late_fee_form':      late_fee_form,
        'waive_late_fee_form': waive_late_fee_form,
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
        'attendance_sessions': attendance_sessions,
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
            StudentNotification.create(
                student=record.student,
                notif_type=StudentNotification.NotificationType.PAYMENT_RECORDED,
                title=f'Payment of ${record.amount:,.2f} recorded',
                body=f'Payment method: {record.get_method_display()}. Check your payment history for details.',
                link='/register/form/#payment',
            )
            messages.success(request, f'Payment of ${record.amount} recorded.')
            return redirect(f"{reverse('staff_student_detail', args=[pk])}?new_payment={record.pk}")
        else:
            messages.error(request, 'Please correct the errors below.')
    return redirect('staff_student_detail', pk=pk)


@staff_required
def add_late_fee(request, pk):
    student = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    if request.method == 'POST':
        form = LatePaymentFeeForm(request.POST)
        if form.is_valid():
            fee = form.save(commit=False)
            fee.student = student
            fee.recorded_by = request.user
            fee.save()
            messages.success(request, f'{fee.get_fee_type_display()} of ${fee.amount} added.')
        else:
            messages.error(request, 'Please correct the errors below.')
    return redirect(f"{reverse('staff_student_detail', args=[pk])}#late-fees")


@staff_required
def axes_lockouts(request):
    from axes.models import AccessAttempt
    from axes.utils import reset

    if request.method == 'POST':
        ip = request.POST.get('ip_address')
        username = request.POST.get('username')
        if ip:
            reset(ip=ip)
            messages.success(request, f'Lockout reset for IP {ip}.')
        return redirect('staff_axes_lockouts')

    attempts = AccessAttempt.objects.order_by('-attempt_time')[:100]
    return render(request, 'staff/axes_lockouts.html', {
        'attempts': attempts,
        'failure_limit': settings.AXES_FAILURE_LIMIT,
    })


@staff_required
def waive_late_fee(request, pk, fee_id):
    student = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)
    fee = get_object_or_404(LatePaymentFee, pk=fee_id, student=student)
    if request.method == 'POST':
        form = WaiveLateFeeForm(request.POST)
        if form.is_valid():
            fee.waived = True
            fee.waived_by = request.user
            fee.waived_reason = form.cleaned_data['waived_reason']
            fee.save()
            messages.success(request, f'{fee.get_fee_type_display()} waived.')
        else:
            messages.error(request, 'Please provide a reason for waiving this fee.')
    return redirect(f"{reverse('staff_student_detail', args=[pk])}#late-fees")


@staff_required
def payment_receipt_pdf(request, payment_id):
    payment = get_object_or_404(PaymentHistory, pk=payment_id)
    from students.payment_pdf import generate_payment_receipt
    pdf_bytes = generate_payment_receipt(payment)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Receipt_{payment.pk}.pdf"'
    return response


@staff_required
def staff_attendance_pdf(request, session_id):
    session = get_object_or_404(AttendanceRecord, pk=session_id)
    from instructor.attendance_pdf import generate_attendance_pdf
    pdf_bytes = generate_attendance_pdf(session)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Attendance_{session.session_date}.pdf"'
    return response


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
        if doc.status == StudentDocument.Status.APPROVED:
            StudentNotification.create(
                student=doc.student,
                notif_type=StudentNotification.NotificationType.DOCUMENT_APPROVED,
                title=f'Your {doc.doc_type.label} has been approved',
                body='Your document has been reviewed and approved by PEMSE staff.',
                link='/documents/',
            )
        elif doc.status == StudentDocument.Status.REJECTED:
            StudentNotification.create(
                student=doc.student,
                notif_type=StudentNotification.NotificationType.DOCUMENT_REJECTED,
                title=f'Your {doc.doc_type.label} needs to be re-uploaded',
                body=f'Reason: {doc.notes}' if doc.notes else 'Please re-upload this document.',
                link='/documents/',
            )
        messages.success(request, f'{doc.doc_type.label} marked as {doc.status}.')
    return redirect('staff_student_detail', pk=doc.student_id)


@staff_required
def bulk_approve_documents(request):
    if request.method != 'POST':
        return redirect('staff_dashboard')
    doc_ids = request.POST.getlist('doc_ids')
    docs_to_approve = list(StudentDocument.objects.filter(
        pk__in=doc_ids,
        status=StudentDocument.Status.PENDING,
    ).select_related('student', 'doc_type'))
    updated = StudentDocument.objects.filter(
        pk__in=[d.pk for d in docs_to_approve],
    ).update(
        status=StudentDocument.Status.APPROVED,
        reviewed_at=timezone.now(),
        reviewed_by=request.user,
    )
    for doc in docs_to_approve:
        StudentNotification.create(
            student=doc.student,
            notif_type=StudentNotification.NotificationType.DOCUMENT_APPROVED,
            title=f'Your {doc.doc_type.label} has been approved',
            body='Your document has been reviewed and approved by PEMSE staff.',
            link='/documents/',
        )
    messages.success(request, f'{updated} document(s) approved successfully.')
    return redirect(request.POST.get('next') or 'staff_dashboard')


@staff_required
def document_review_queue(request):
    pending_docs = StudentDocument.objects.filter(
        status=StudentDocument.Status.PENDING,
    ).select_related('student', 'doc_type').order_by('uploaded_at')
    return render(request, 'staff/document_queue.html', {'pending_docs': pending_docs})


@staff_required
def export_students_csv(request):
    import csv
    from django.http import StreamingHttpResponse
    from students.balance import compute_balance

    course_filter = request.GET.get('course', '')
    status_filter = request.GET.get('status', '')

    students = Student.objects.filter(
        role=Student.Role.STUDENT
    ).select_related('enrollment__course').order_by(
        'enrollment__course__option_number', 'last_name', 'first_name'
    )
    if course_filter:
        students = students.filter(enrollment__course__option_number=course_filter)
    if status_filter:
        students = students.filter(enroll_status=status_filter)

    def generate_rows():
        yield [
            'Last Name', 'First Name', 'Email', 'Phone',
            'Course', 'Enrollment Status', 'Registration Submitted',
            'Handbook Signed', 'Contract Signed',
            'Documents Uploaded', 'Total Paid', 'Balance Due',
            'Date Joined', 'Confirmation Number'
        ]
        for s in students:
            enrollment, total_paid, total_owed, balance_due = compute_balance(s)
            doc_count = s.documents.filter(doc_type__required=True).count()
            yield [
                s.last_name, s.first_name, s.email, s.phone,
                enrollment.course.name if enrollment else '',
                s.get_enroll_status_display(),
                'Yes' if s.reg_submitted else 'No',
                'Yes' if s.handbook_signed else 'No',
                'Yes' if s.contract_signed else 'No',
                f'{doc_count}/4',
                f'${total_paid:,.2f}',
                f'${balance_due:,.2f}',
                s.date_joined.strftime('%Y-%m-%d'),
                s.reg_conf_number,
            ]

    class Echo:
        def write(self, value):
            return value

    writer = csv.writer(Echo())
    response = StreamingHttpResponse(
        (writer.writerow(row) for row in generate_rows()),
        content_type='text/csv'
    )
    filename = f'PEMSE_Students_{timezone.now().strftime("%Y%m%d")}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


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
        if ann.schedule_status == 'live':
            target_students = Student.objects.filter(role=Student.Role.STUDENT)
            if ann.course:
                target_students = target_students.filter(enrollment__course=ann.course)
            for student in target_students:
                StudentNotification.create(
                    student=student,
                    notif_type=StudentNotification.NotificationType.ANNOUNCEMENT,
                    title=ann.title,
                    body=ann.body[:200],
                    link='/dashboard/',
                )
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
# (staff_student_pdf now routes to students.views.registration_pdf_view — see staff/urls.py)


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
        days_remaining = (deadline - today).days if deadline else None
        rows.append({
            'course':   c,
            'report':   report,
            'deadline': deadline,
            'overdue':  overdue,
            'soon':     soon,
            'days_remaining': days_remaining,
            'days_overdue':   -days_remaining if days_remaining is not None and days_remaining < 0 else None,
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


@staff_required
def dhhs_report_pdf(request, report_id):
    from students.models import CourseReportRecord
    from students.dhhs_pdf import generate_dhhs_report
    report = get_object_or_404(CourseReportRecord, pk=report_id)
    pdf_bytes = generate_dhhs_report(report)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    course_name = report.course.name.replace(' ', '_')[:30]
    response['Content-Disposition'] = f'inline; filename="DHHS_Report_{course_name}.pdf"'
    return response


@staff_required
def mark_report_submitted(request, report_id):
    from students.models import CourseReportRecord
    report = get_object_or_404(CourseReportRecord, pk=report_id)
    if request.method == 'POST':
        report.report_submitted_to_department = True
        report.report_submitted_date = timezone.now().date()
        report.save(update_fields=['report_submitted_to_department', 'report_submitted_date'])
        messages.success(request, f'{report.course.name} marked as submitted to DHHS.')
    return redirect('staff_course_reports')


# ── NREMT Pass Rates ──────────────────────────────────────────────────────────

def _nremt_overall_stats():
    """2-year aggregate NREMT cognitive pass rate — 172 NAC 13-004(E), 75% minimum."""
    from datetime import date, timedelta

    two_years_ago = date.today() - timedelta(days=730)
    records = CourseCompletionRecord.objects.filter(
        completion_date__gte=two_years_ago, withdrew=False,
    )
    total_passed = records.filter(nremt_cognitive_result='pass').count()
    total_failed = records.filter(nremt_cognitive_result='fail').count()
    total_tested = total_passed + total_failed
    overall_rate = round(total_passed / total_tested * 100, 1) if total_tested else None
    pending_count = CourseCompletionRecord.objects.filter(nremt_cognitive_result='pending').count()
    return {
        'overall_rate':  overall_rate,
        'compliant':     overall_rate is not None and overall_rate >= 75,
        'total_passed':  total_passed,
        'total_tested':  total_tested,
        'pending_count': pending_count,
        'two_years_ago': two_years_ago,
    }


@staff_required
def pass_rates(request):
    """NREMT cognitive-exam pass rate tracker — 75% minimum aggregate over 2 years (172 NAC 13-004(E))."""
    from datetime import date, timedelta

    two_years_ago = date.today() - timedelta(days=730)

    # Group completed (non-withdrawn) records by course + completion year
    records = CourseCompletionRecord.objects.filter(
        completion_date__gte=two_years_ago,
        withdrew=False,
    ).select_related('course', 'student')

    course_stats = {}
    for record in records:
        key = (record.course.id, record.completion_date.year)
        if key not in course_stats:
            course_stats[key] = {
                'course': record.course,
                'year': record.completion_date.year,
                'total_completed': 0,
                'nremt_passed': 0,
                'nremt_failed': 0,
                'nremt_pending': 0,
            }
        course_stats[key]['total_completed'] += 1
        if record.nremt_cognitive_result == 'pass':
            course_stats[key]['nremt_passed'] += 1
        elif record.nremt_cognitive_result == 'fail':
            course_stats[key]['nremt_failed'] += 1
        else:
            course_stats[key]['nremt_pending'] += 1

    stats_list = []
    for stat in course_stats.values():
        tested = stat['nremt_passed'] + stat['nremt_failed']
        stat['pass_rate'] = round(stat['nremt_passed'] / tested * 100, 1) if tested else None
        stat['meets_requirement'] = stat['pass_rate'] is not None and stat['pass_rate'] >= 75
        stats_list.append(stat)

    overall = _nremt_overall_stats()

    pending_records = CourseCompletionRecord.objects.filter(
        nremt_cognitive_result='pending',
    ).select_related('student', 'course').order_by('-completion_date')

    return render(request, 'staff/pass_rates.html', {
        'stats_list': sorted(stats_list, key=lambda x: (x['year'], x['course'].option_number)),
        'overall_rate': overall['overall_rate'],
        'compliant': overall['compliant'],
        'total_passed': overall['total_passed'],
        'total_tested': overall['total_tested'],
        'requirement': 75,
        'two_years_ago': overall['two_years_ago'],
        'pending_records': pending_records,
    })


@staff_required
def pass_rates_quick_update(request, record_id):
    record = get_object_or_404(CourseCompletionRecord, pk=record_id)
    if request.method == 'POST':
        result = request.POST.get('result')
        if result in ('pass', 'fail'):
            record.nremt_cognitive_result = result
            record.nremt_cognitive_date = timezone.now().date()
            record.save(update_fields=['nremt_cognitive_result', 'nremt_cognitive_date'])
            messages.success(request, f"{record.student.get_full_name()}'s NREMT result recorded as {result}.")
    return redirect('staff_pass_rates')


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
        license_days_left = None
        if inst.instructor_license_expiry:
            license_days_left = (inst.instructor_license_expiry - today).days
            if license_days_left < 0:
                license_status = 'expired'
            elif license_days_left <= 90:
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
            'license_days_left': license_days_left,
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
