from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from schedule.models import CalendarEvent
from students.models import StudentNotification
from courses.models import CourseEnrollment


class Command(BaseCommand):
    help = 'Create deadline reminder notifications for students with upcoming quiz/exam deadlines'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        created = 0

        for days_ahead in [7, 2, 1]:
            target_date = today + timedelta(days=days_ahead)
            events = CalendarEvent.objects.filter(
                date=target_date,
                event_type__in=[
                    CalendarEvent.EventType.QUIZ,
                    CalendarEvent.EventType.EXAM,
                    CalendarEvent.EventType.DUE_DATE,
                ]
            ).select_related('course')

            for event in events:
                # Find all enrolled students in this course
                enrollments = CourseEnrollment.objects.filter(
                    course=event.course
                ).select_related('student')

                if days_ahead == 1:
                    label = 'due tomorrow'
                elif days_ahead == 2:
                    label = 'due in 2 days'
                else:
                    label = f'due in {days_ahead} days'
                title = f'Reminder: {event.title} is {label}'

                for enrollment in enrollments:
                    student = enrollment.student
                    # Check if we already sent this exact reminder today
                    already_sent = StudentNotification.objects.filter(
                        student=student,
                        notif_type=StudentNotification.NotificationType.DEADLINE_REMINDER,
                        title=title,
                        created_at__date=today,
                    ).exists()
                    if already_sent:
                        continue

                    StudentNotification.create(
                        student=student,
                        notif_type=StudentNotification.NotificationType.DEADLINE_REMINDER,
                        title=title,
                        body=f'Due: {event.date.strftime("%A, %B %d, %Y")}. Log in to complete it before the deadline.',
                        link='/calendar/',
                    )
                    created += 1

        self.stdout.write(self.style.SUCCESS(f'Created {created} deadline reminder notifications'))
