from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from students.balance import compute_balance
from students.models import Student, StudentNotification

GRACE_PERIOD_DAYS = 30


class Command(BaseCommand):
    help = (
        'Flags active students with an overdue balance for staff review. '
        'Does NOT apply late fees automatically — staff must add them manually.'
    )

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        cutoff = today - timedelta(days=GRACE_PERIOD_DAYS)
        flagged = 0

        students = Student.objects.filter(
            role=Student.Role.STUDENT, enroll_status='active',
        )
        for student in students:
            enrollment, _, _, balance_due = compute_balance(student)
            if not enrollment or balance_due <= 0:
                continue
            if enrollment.enrolled_at and enrollment.enrolled_at.date() > cutoff:
                continue

            title = f'{student.get_full_name()} has an overdue balance'
            for staff_user in Student.objects.filter(
                role__in=[Student.Role.STAFF, Student.Role.ADMIN]
            ):
                already_notified = StudentNotification.objects.filter(
                    student=staff_user, notif_type='general', title=title, is_read=False,
                ).exists()
                if not already_notified:
                    StudentNotification.create(
                        student=staff_user,
                        notif_type='general',
                        title=title,
                        body=f'Balance due: ${balance_due:,.2f}. Review for a late fee per handbook policy.',
                        link=f'/staff/students/{student.pk}/#late-fees',
                    )
            flagged += 1

        self.stdout.write(self.style.SUCCESS(f'Flagged {flagged} student(s) with overdue balances for staff review'))
