from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q
import uuid

from .models import (
    Student, PaymentRecord, Announcement, PaymentHistory,
    CognitiveExamRecord, PsychomotorSkillRecord, PatientContactRecord,
)
from .forms import StudentRegistrationForm, StudentLoginForm, ProfileForm, PaymentForm
from .emails import send_instructor_registration_notifications, send_registration_confirmation
from courses.models import CourseEnrollment
from documents.models import StudentDocument, DocumentType
from handbook.models import HandbookChapter
from instructor.models import AttendanceRecord, StudentAttendance
from schedule.models import CalendarEvent


def landing_view(request):
    if request.user.is_authenticated:
        if request.user.is_instructor:
            return redirect('instructor_dashboard')
        if request.user.is_office_staff:
            return redirect('staff_dashboard')
        return redirect('dashboard')
    return render(request, 'landing.html')


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_office_staff:
            return redirect('staff_dashboard')
        if request.user.is_instructor:
            return redirect('instructor_dashboard')
        return redirect('dashboard')
    form = StudentLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        next_url = request.GET.get('next')
        if next_url:
            return redirect(next_url)
        if user.is_office_staff:
            return redirect('staff_dashboard')
        if user.is_instructor:
            return redirect('instructor_dashboard')
        return redirect('dashboard')
    return render(request, 'students/login.html', {'form': form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'students/register_closed.html')


def register_with_invite(request, token):
    """Registration view pre-filled from a staff invitation link."""
    from staff.models import StudentInvitation
    try:
        invitation = StudentInvitation.objects.get(token=token)
    except StudentInvitation.DoesNotExist:
        messages.error(request, 'This invitation link is invalid.')
        return redirect('register')

    if not invitation.is_valid:
        messages.error(request, 'This invitation link has expired or has already been used.')
        return redirect('register')

    if request.user.is_authenticated:
        return redirect('dashboard')

    initial = {'email': invitation.email}
    form = StudentRegistrationForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        student = form.save()
        if invitation.course:
            CourseEnrollment.objects.get_or_create(student=student, defaults={'course': invitation.course})
        invitation.used    = True
        invitation.used_at = timezone.now()
        invitation.save()
        login(request, student, backend='students.backends.EmailBackend')
        messages.success(request, f'Welcome, {student.first_name}! Complete your enrollment below.')
        return redirect('dashboard')

    return render(request, 'students/register.html', {
        'form': form,
        'invite_email': invitation.email,
        'invite_course': invitation.course,
    })


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard_view(request):
    if request.user.is_office_staff:
        return redirect('staff_dashboard')
    if request.user.is_instructor:
        return redirect('instructor_dashboard')

    student = request.user
    enrollment = CourseEnrollment.objects.filter(student=student).first()
    docs = StudentDocument.objects.filter(student=student).select_related('doc_type')
    doc_types = DocumentType.objects.all()
    announcements = Announcement.objects.filter(is_active=True)[:6]
    chapters = HandbookChapter.objects.filter(is_active=True).count()

    # Checklist items
    tasks = [
        {
            'label': 'Complete registration form',
            'done': student.reg_submitted,
            'url': '/register/form/',
            'icon': 'file-text',
        },
        {
            'label': 'Sign student handbook',
            'done': student.handbook_signed,
            'url': '/handbook/',
            'icon': 'book-open',
        },
        {
            'label': 'Upload required documents',
            'done': docs.filter(doc_type__required=True).count() >= 3,
            'url': '/documents/',
            'icon': 'upload-cloud',
        },
        {
            'label': 'Sign payment contract',
            'done': student.contract_signed,
            'url': '/register/form/#payment',
            'icon': 'pen-tool',
        },
    ]
    done_count = sum(1 for t in tasks if t['done'])

    if not student.reg_submitted:
        next_action = {'label': 'Complete your registration form', 'url': '/register/form/', 'icon': 'bi-file-earmark-text'}
    elif not student.handbook_signed:
        next_action = {'label': 'Sign the student handbook', 'url': '/handbook/', 'icon': 'bi-book-fill'}
    elif docs.filter(doc_type__required=True).count() < 3:
        next_action = {'label': 'Upload your required documents', 'url': '/documents/', 'icon': 'bi-upload'}
    elif not student.contract_signed:
        next_action = {'label': 'Sign your payment contract', 'url': '/register/form/#payment', 'icon': 'bi-pen-fill'}
    else:
        next_action = None

    payment_history = student.payment_history.all()
    from decimal import Decimal
    total_paid = sum(p.amount for p in payment_history)
    total_owed = enrollment.total_tuition if enrollment else Decimal('0')
    balance_due = max(Decimal('0'), total_owed - total_paid)

    # Clinical rotations summary (no scores shown to student)
    from evaluations.models import ClinicalRotation, PreceptorEvaluation
    rotations = ClinicalRotation.objects.filter(student=student)
    pending_preceptor_evals = PreceptorEvaluation.objects.filter(
        rotation__student=student, status=PreceptorEvaluation.Status.PENDING
    ).count()

    progress = _build_progress_summary(student, enrollment)
    upcoming_deadlines = _build_upcoming_deadlines(student)
    next_class = CalendarEvent.next_session(student.calendar_courses)

    return render(request, 'students/dashboard.html', {
        'student':                student,
        'enrollment':             enrollment,
        'docs':                   docs,
        'doc_types':              doc_types,
        'announcements':          announcements,
        'tasks':                  tasks,
        'done_count':             done_count,
        'next_action':            next_action,
        'total_tasks':            len(tasks),
        'payment_history':        payment_history,
        'total_paid':             total_paid,
        'total_owed':             total_owed,
        'balance_due':            balance_due,
        'rotation_count':         rotations.count(),
        'pending_preceptor_evals': pending_preceptor_evals,
        'progress':               progress,
        'upcoming_deadlines':     upcoming_deadlines,
        'next_class':             next_class,
    })


def _build_upcoming_deadlines(student):
    """Next 5 upcoming quiz/exam/due-date CalendarEvents across the student's courses, with a countdown label."""
    today = timezone.now().date()
    events = CalendarEvent.objects.filter(
        course__in=student.calendar_courses,
        event_type__in=[CalendarEvent.EventType.QUIZ, CalendarEvent.EventType.EXAM, CalendarEvent.EventType.DUE_DATE],
        date__gte=today,
    ).order_by('date')[:5]

    deadlines = []
    for event in events:
        days = (event.date - today).days
        if days == 0:
            countdown = 'Due today'
        elif days == 1:
            countdown = 'Due tomorrow'
        else:
            countdown = f'Due in {days} days'

        if days <= 1:
            color = 'red'
        elif days <= 7:
            color = 'yellow'
        else:
            color = 'blue'

        deadlines.append({'event': event, 'countdown': countdown, 'color': color})
    return deadlines


def _pct(value, total):
    if not total:
        return 0
    return min(100, round(value / total * 100))


def _build_progress_summary(student, enrollment):
    """Compute the dashboard's attendance/contacts/skills/exams progress bars."""
    attendance_entries = StudentAttendance.objects.filter(
        student=student, status__in=['present', 'late', 'makeup'],
    ).select_related('session')
    sessions_attended = attendance_entries.count()
    total_sessions = AttendanceRecord.objects.filter(course__in=student.calendar_courses).count()
    attendance_pct = round((sessions_attended / total_sessions * 100) if total_sessions else 0)

    contacts_required = 25 if (enrollment and enrollment.course.licensure == 'AEMT') else 5
    patient_contacts = PatientContactRecord.objects.filter(student=student).count()

    skills_passed = PsychomotorSkillRecord.objects.filter(
        student=student, passed=True,
    ).values('skill_name').distinct().count()
    skills_attempted = PsychomotorSkillRecord.objects.filter(
        student=student,
    ).values('skill_name').distinct().count()

    exams_passed = CognitiveExamRecord.objects.filter(student=student, passed=True).count()
    exams_total = CognitiveExamRecord.objects.filter(student=student).values('exam_name').distinct().count()

    return [
        {
            'label': 'Attendance',
            'value': sessions_attended,
            'display': f'{sessions_attended} of {total_sessions} sessions ({attendance_pct}%)',
            'pct': attendance_pct,
        },
        {
            'label': 'Patient contacts',
            'value': patient_contacts,
            'display': f'{patient_contacts} of {contacts_required} required',
            'pct': _pct(patient_contacts, contacts_required),
        },
        {
            'label': 'Skills completed',
            'value': skills_passed,
            'display': f'{skills_passed} skills passed',
            'pct': _pct(skills_passed, skills_attempted),
        },
        {
            'label': 'Exams',
            'value': exams_passed,
            'display': f'{exams_passed} of {exams_total} passed',
            'pct': _pct(exams_passed, exams_total),
        },
    ]


@login_required
def profile_view(request):
    student = request.user
    form = ProfileForm(request.POST or None, instance=student)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')
    return render(request, 'students/profile.html', {'form': form})


@login_required
def calendar_view(request):
    from schedule.models import CalendarEvent

    student = request.user
    events = CalendarEvent.objects.filter(
        course__in=student.calendar_courses
    ).select_related('course').order_by('date', 'start_time')

    today = timezone.now().date()
    return render(request, 'students/calendar.html', {
        'upcoming_events': [e for e in events if e.date >= today],
        'past_events':     [e for e in events if e.date < today],
        'feed_token':      student.calendar_token,
        'has_course':      student.calendar_courses.exists(),
    })


@login_required
def registration_form_view(request):
    """Multi-step registration form with payment contract."""
    from courses.models import Course
    student = request.user
    enrollment = CourseEnrollment.objects.filter(student=student).first()
    payment, _ = PaymentRecord.objects.get_or_create(student=student)
    courses = [c for c in Course.objects.filter(is_active=True) if c.registration_open]

    pay_form = PaymentForm(request.POST or None, instance=payment)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_payment' and pay_form.is_valid():
            pay_form.save()
            messages.success(request, 'Payment information saved.')

        elif action == 'sign_contract':
            sig_name = request.POST.get('sig_name', '').strip()
            if not sig_name or len(sig_name) < 500:
                messages.error(request, 'Please draw your signature before signing.')
            elif not enrollment:
                messages.error(request, 'Please select a course before signing.')
            else:
                student.contract_signed = True
                student.contract_sig_name = sig_name
                student.contract_signed_at = timezone.now()
                student.save(update_fields=['contract_signed', 'contract_sig_name', 'contract_signed_at'])
                messages.success(request, 'Payment contract signed successfully.')

        elif action == 'submit_registration':
            if not student.contract_signed:
                messages.error(request, 'Please sign the payment contract first.')
            elif not enrollment:
                messages.error(request, 'Please select a course first.')
            else:
                conf = f'PEMSE-{timezone.now().year}-{str(uuid.uuid4())[:8].upper()}'
                student.reg_submitted = True
                student.reg_submitted_at = timezone.now()
                student.reg_conf_number = conf
                student.save(update_fields=['reg_submitted', 'reg_submitted_at', 'reg_conf_number'])
                messages.success(request, f'Registration submitted! Confirmation: {conf}')
                send_registration_confirmation(student, enrollment, conf)
                send_instructor_registration_notifications(student, enrollment, conf)
                return redirect('dashboard')

        return redirect('registration_form')

    return render(request, 'students/registration_form.html', {
        'student':    student,
        'enrollment': enrollment,
        'pay_form':   pay_form,
        'payment':    payment,
        'courses':    courses,
    })


@login_required
def registration_pdf_view(request, student_id=None):
    if student_id:
        # Staff accessing any student's PDF
        if not request.user.is_office_staff:
            return HttpResponseForbidden()
        student = get_object_or_404(Student, pk=student_id)
    else:
        # Student accessing their own PDF
        student = request.user
    from .pdf import generate_registration_pdf
    pdf_bytes = generate_registration_pdf(student)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    safe_name = student.get_full_name().replace(' ', '_')
    response['Content-Disposition'] = f'inline; filename="PEMSE_Registration_{safe_name}.pdf"'
    return response
