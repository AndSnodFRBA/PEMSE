"""
python manage.py course_usage_report

Read-only report of every Course and what's attached to it (enrollments,
gradebooks, calendar events, instructor assignments) — used to check
whether a course is safe to delete before doing so.
"""
from django.core.management.base import BaseCommand

from courses.models import Course


class Command(BaseCommand):
    help = 'Report enrollment/schedule/grade usage for every course.'

    def handle(self, *args, **options):
        from schedule.models import CalendarEvent
        from grades.models import GradeBook
        from instructor.models import InstructorCourseAssignment

        courses = Course.objects.order_by('option_number')
        if not courses:
            self.stdout.write('No courses found.')
            return

        for c in courses:
            enrollments = c.enrollments.count()
            events = CalendarEvent.objects.filter(course=c).count()
            gradebooks = GradeBook.objects.filter(course=c).count()
            assignments = InstructorCourseAssignment.objects.filter(course=c).count()
            self.stdout.write(
                f'Option {c.option_number} — {c.name} (id={c.pk}, active={c.is_active}): '
                f'{enrollments} enrollment(s), {events} calendar event(s), '
                f'{gradebooks} gradebook(s), {assignments} instructor assignment(s)'
            )
