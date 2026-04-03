from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
import uuid

from .models import Student, PaymentRecord, Announcement, PaymentHistory
from .forms import StudentRegistrationForm, StudentLoginForm, ProfileForm, PaymentForm
from courses.models import CourseEnrollment
from documents.models import StudentDocument, DocumentType
from handbook.models import HandbookChapter


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_office_staff:
            return redirect('staff_dashboard')
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
        return redirect('dashboard')
    return render(request, 'students/login.html', {'form': form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = StudentRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        student = form.save()
        login(request, student, backend='students.backends.EmailBackend')
        messages.success(request, f'Welcome, {student.first_name}! Complete your enrollment below.')
        return redirect('dashboard')
    return render(request, 'students/register.html', {'form': form})


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
        invitation.used    = True
        invitation.used_at = timezone.now()
        invitation.save()
        login(request, student, backend='students.backends.EmailBackend')
        messages.success(request, f'Welcome, {student.first_name}! Complete your enrollment below.')
        return redirect('dashboard')

    return render(request, 'students/register.html', {'form': form, 'invite_email': invitation.email})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard_view(request):
    if request.user.is_office_staff:
        return redirect('staff_dashboard')

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

    payment_history = student.payment_history.all()
    from decimal import Decimal
    total_paid = sum(p.amount for p in payment_history)
    total_owed = enrollment.course.price if enrollment else Decimal('0')
    balance_due = max(Decimal('0'), total_owed - total_paid)

    return render(request, 'students/dashboard.html', {
        'student':         student,
        'enrollment':      enrollment,
        'docs':            docs,
        'doc_types':       doc_types,
        'announcements':   announcements,
        'tasks':           tasks,
        'done_count':      done_count,
        'total_tasks':     len(tasks),
        'payment_history': payment_history,
        'total_paid':      total_paid,
        'total_owed':      total_owed,
        'balance_due':     balance_due,
    })


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
                conf = f'PEMSE-2025-{str(uuid.uuid4())[:8].upper()}'
                student.reg_submitted = True
                student.reg_submitted_at = timezone.now()
                student.reg_conf_number = conf
                student.save(update_fields=['reg_submitted', 'reg_submitted_at', 'reg_conf_number'])
                messages.success(request, f'Registration submitted! Confirmation: {conf}')
                # TODO: send_registration_email(student)
                return redirect('dashboard')

        return redirect('registration_form')

    return render(request, 'students/registration_form.html', {
        'student':    student,
        'enrollment': enrollment,
        'pay_form':   pay_form,
        'payment':    payment,
        'courses':    courses,
    })
