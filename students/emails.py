"""Transactional emails sent to students.

Each function fails safe: SMTP errors are logged, never raised, so a
flaky mail send can't break a staff action or a student's registration
submission.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _automated_notice():
    return (
        f'This is an automated message sent by the {settings.AGENCY_SHORT_NAME} Student Portal. '
        f'Please do not reply directly to this email — contact {settings.AGENCY_SHORT_NAME} at '
        f'{settings.AGENCY_EMAIL} instead.'
    )


def _send(subject, body, to_email):
    if not to_email:
        return
    full_body = f'{body}\n\n---\n{_automated_notice()}'
    try:
        send_mail(
            subject=f'{settings.AGENCY_SHORT_NAME} — {subject}',
            message=full_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception('Failed to send email "%s" to %s', subject, to_email)


def send_registration_confirmation(student, enrollment, conf_number):
    course = enrollment.course if enrollment else None
    lines = [
        f'Hi {student.first_name or student.get_full_name()},',
        '',
        f'Your {settings.AGENCY_SHORT_NAME} registration has been submitted successfully.',
        '',
        f'Confirmation number: {conf_number}',
    ]
    if course:
        lines += [
            f'Course: Option {course.option_number} — {course.name}',
            f'Total tuition: ${enrollment.total_tuition:,.0f}',
            f'Minimum down payment: ${course.min_down:,.0f} (due before first night of class)',
        ]
    lines += [
        '',
        f'If you have any questions, contact {settings.AGENCY_SHORT_NAME} at {settings.AGENCY_EMAIL}.',
        '',
        f'— {settings.AGENCY_NAME}',
    ]
    _send('Registration confirmed', '\n'.join(lines), student.email)


def send_instructor_registration_notifications(student, enrollment, conf_number):
    """Notify every instructor actively assigned to the student's course that
    the student has completed registration."""
    if not enrollment:
        return
    from instructor.models import InstructorCourseAssignment

    course = enrollment.course
    assignments = InstructorCourseAssignment.objects.filter(
        course=course, is_active=True
    ).select_related('instructor')
    for assignment in assignments:
        instructor = assignment.instructor
        lines = [
            f'Hi {instructor.first_name or instructor.get_full_name()},',
            '',
            f'{student.get_full_name()} has completed registration for '
            f'Option {course.option_number} — {course.name}.',
            '',
            f'Confirmation number: {conf_number}',
            f'Email: {student.email}',
            f'Phone: {student.phone or "—"}',
            '',
            f'— {settings.AGENCY_NAME}',
        ]
        _send('Student registration completed', '\n'.join(lines), instructor.email)


def send_invitation_email(invitation, invite_link):
    lines = [
        f"You've been invited to register for a course with {settings.AGENCY_NAME}.",
    ]
    if invitation.course:
        c = invitation.course
        lines += [
            '',
            f'Course: Option {c.option_number} — {c.name}',
            f'Base tuition: ${c.price:,.0f}',
        ]
    lines += [
        '',
        f'Create your account here: {invite_link}',
        '',
        f'This link expires {invitation.expires_at.strftime("%B %d, %Y")} and can only be used once.',
        '',
        'If you weren\'t expecting this invitation, you can ignore this email.',
        '',
        f'— {settings.AGENCY_NAME}',
    ]
    _send("You're invited to register", '\n'.join(lines), invitation.email)


def send_staff_invitation_email(invitation, invite_link):
    lines = [
        f"You've been invited to set up an office staff account with {settings.AGENCY_NAME}.",
        '',
        f'Set up your account here: {invite_link}',
        '',
        f'This link expires {invitation.expires_at.strftime("%B %d, %Y")} and can only be used once.',
        '',
        'If you weren\'t expecting this invitation, you can ignore this email.',
        '',
        f'— {settings.AGENCY_NAME}',
    ]
    _send("You're invited to join the staff portal", '\n'.join(lines), invitation.email)


def send_document_review_notification(doc):
    student = doc.student
    if doc.status == doc.Status.APPROVED:
        headline = f'Your "{doc.doc_type.label}" has been approved.'
    elif doc.status == doc.Status.REJECTED:
        headline = f'Your "{doc.doc_type.label}" was rejected and needs to be re-uploaded.'
    else:
        return  # pending — nothing to notify about

    lines = [
        f'Hi {student.first_name or student.get_full_name()},',
        '',
        headline,
    ]
    if doc.notes:
        lines += ['', f'Reviewer notes: {doc.notes}']
    lines += [
        '',
        'Log in to your student portal to view details or re-upload if needed.',
        '',
        f'— {settings.AGENCY_NAME}',
    ]
    _send('Document review update', '\n'.join(lines), student.email)


def registration_incomplete_reminder_content(student):
    subject = 'Finish your registration'
    lines = [
        f'Hi {student.first_name or student.get_full_name()},',
        '',
        f"We noticed your {settings.AGENCY_SHORT_NAME} registration isn't complete yet. Please log in to your student "
        'portal and finish up the remaining steps (course selection, payment contract, handbook, '
        'and required documents) as soon as you can.',
        '',
        f'Questions? Contact {settings.AGENCY_SHORT_NAME} at {settings.AGENCY_EMAIL}.',
        '',
        f'— {settings.AGENCY_NAME}',
    ]
    return subject, '\n'.join(lines)


def balance_due_reminder_content(student, balance_due):
    subject = f'Balance due on your {settings.AGENCY_SHORT_NAME} tuition'
    lines = [
        f'Hi {student.first_name or student.get_full_name()},',
        '',
        f'This is a reminder that you have an outstanding balance of ${balance_due:,.2f} on your {settings.AGENCY_SHORT_NAME} tuition.',
        '',
        f'Please contact {settings.AGENCY_SHORT_NAME} to arrange payment or if you have questions about your payment schedule.',
        '',
        settings.AGENCY_EMAIL,
        '',
        f'— {settings.AGENCY_NAME}',
    ]
    return subject, '\n'.join(lines)


def course_start_reminder_content(student, course, days_before):
    when = 'tomorrow' if days_before == 1 else f'in {days_before} days'
    subject = f'Your course starts {when}'
    lines = [
        f'Hi {student.first_name or student.get_full_name()},',
        '',
        f'Option {course.option_number} — {course.name} starts {when}',
        f'({course.start_date.strftime("%B %d, %Y")}).',
    ]
    if course.location_display:
        lines.append(f'Location: {course.location_display}')
    lines += [
        '',
        'Make sure your registration, payment, and required documents are all up to date before class begins.',
        '',
        f'Questions? Contact {settings.AGENCY_SHORT_NAME} at {settings.AGENCY_EMAIL}.',
        '',
        f'— {settings.AGENCY_NAME}',
    ]
    return subject, '\n'.join(lines)


def send_payment_receipt(payment_record):
    student = payment_record.student
    total_paid = sum(p.amount for p in student.payment_history.all())
    enrollment = getattr(student, 'enrollment', None)
    lines = [
        f'Hi {student.first_name or student.get_full_name()},',
        '',
        f'We recorded a payment of ${payment_record.amount:,.2f} on {payment_record.payment_date}.',
        f'Method: {payment_record.get_method_display()}',
        '',
        f'Total paid to date: ${total_paid:,.2f}',
    ]
    if enrollment:
        balance = max(0, enrollment.total_tuition - total_paid)
        lines.append(f'Remaining balance: ${balance:,.2f}')
    lines += [
        '',
        f'Questions about your balance? Contact {settings.AGENCY_SHORT_NAME} at {settings.AGENCY_EMAIL}.',
        '',
        f'— {settings.AGENCY_NAME}',
    ]
    _send('Payment received', '\n'.join(lines), student.email)
