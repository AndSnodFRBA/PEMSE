"""python manage.py sync_instructor_license_events

Syncs instructor license expiry dates to the staff calendar as OTHER-type
events, so staff see them alongside the rest of the course schedule.
Safe to re-run — every instructor's event is tagged with a stable
[instructor_id:N] marker in the description, so if a run-to-run title
change (e.g. after a name or license-level update) would otherwise leave
a stale duplicate behind, the old one is cleaned up first.
"""
from django.core.management.base import BaseCommand

from courses.models import Course
from schedule.models import CalendarEvent
from students.models import Student


class Command(BaseCommand):
    help = 'Sync instructor license expiry dates to the staff calendar'

    def handle(self, *args, **kwargs):
        instructors = Student.objects.filter(
            role=Student.Role.INSTRUCTOR,
            instructor_license_expiry__isnull=False,
        )
        # Use the first active course as the anchor for the calendar event —
        # staff see all courses, so it will appear on their calendar.
        default_course = Course.objects.filter(is_active=True).first()
        if not default_course:
            self.stderr.write('No active course found — cannot create calendar events')
            return

        created = 0
        updated = 0
        for instructor in instructors:
            level = instructor.instructor_license_level or 'Unspecified'
            title = f'LICENSE EXPIRY: {instructor.get_full_name()} ({level})'
            tag = f'[instructor_id:{instructor.pk}]'
            description = (
                f'Instructor license expires for {instructor.get_full_name()}. '
                f'License level: {level}. License number: {instructor.instructor_license_number}. '
                f'Contact: {instructor.email} {tag}'
            )

            # Remove any stale event left over from a previous run under an
            # old title (e.g. after a name or license-level change).
            CalendarEvent.objects.filter(
                course=default_course,
                event_type=CalendarEvent.EventType.OTHER,
                description__contains=tag,
            ).exclude(title=title).delete()

            obj, was_created = CalendarEvent.objects.update_or_create(
                course=default_course,
                event_type=CalendarEvent.EventType.OTHER,
                title=title,
                defaults={
                    'date': instructor.instructor_license_expiry,
                    'description': description,
                    'all_day': True,
                    'location': '',
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'Created {created} and updated {updated} instructor license expiry events'
        ))
