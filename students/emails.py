"""Transactional emails sent to students.

Each function fails safe: SMTP errors are logged, never raised, so a
flaky mail send can't break a staff action or a student's registration
submission.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _send(subject, body, to_email):
    if not to_email:
        return
    try:
        send_mail(
            subject=f'PEMSE — {subject}',
            message=body,
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
        'Your PEMSE registration has been submitted successfully.',
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
        'If you have any questions, contact PEMSE at emseducation19@gmail.com.',
        '',
        '— Panhandle EMS Education',
    ]
    _send('Registration confirmed', '\n'.join(lines), student.email)


def send_invitation_email(invitation, invite_link):
    lines = [
        "You've been invited to register for a course with Panhandle EMS Education.",
        '',
        f'Create your account here: {invite_link}',
        '',
        f'This link expires {invitation.expires_at.strftime("%B %d, %Y")} and can only be used once.',
        '',
        'If you weren\'t expecting this invitation, you can ignore this email.',
        '',
        '— Panhandle EMS Education',
    ]
    _send("You're invited to register", '\n'.join(lines), invitation.email)


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
        '— Panhandle EMS Education',
    ]
    _send('Document review update', '\n'.join(lines), student.email)


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
        'Questions about your balance? Contact PEMSE at emseducation19@gmail.com.',
        '',
        '— Panhandle EMS Education',
    ]
    _send('Payment received', '\n'.join(lines), student.email)
