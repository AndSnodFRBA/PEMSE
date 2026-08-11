"""python manage.py archive_completed_courses

Marks courses inactive once they ended more than 30 days ago, then syncs
enrolled students' enroll_status from 'active' to 'complete'/'withdrawn'
based on their CourseCompletionRecord. Intended to run on every deploy,
after migrate. Safe to re-run — every change is gated on current state
(is_active=True / enroll_status='active'), so a second run is a no-op.
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Archive courses that ended 30+ days ago and sync student enroll_status."

    def handle(self, *args, **options):
        from courses.models import Course, CourseEnrollment
        from students.models import CourseCompletionRecord, Student

        cutoff = timezone.now().date() - timedelta(days=30)

        stale_courses = Course.objects.filter(is_active=True, end_date__isnull=False, end_date__lt=cutoff)
        archived_count = 0
        for course in stale_courses:
            course.is_active = False
            course.save(update_fields=['is_active'])
            archived_count += 1
            self.stdout.write(f'Archived course: {course} (ended {course.end_date})')
            logger.info('Archived course %s (ended %s)', course, course.end_date)

        status_changed = 0
        enrollments = CourseEnrollment.objects.filter(
            course__is_active=False, student__enroll_status=Student.EnrollStatus.ACTIVE,
        ).select_related('student', 'course')
        for enrollment in enrollments:
            student = enrollment.student
            record = CourseCompletionRecord.objects.filter(student=student, course=enrollment.course).first()
            if not record:
                continue
            if record.withdrew:
                new_status = Student.EnrollStatus.WITHDRAWN
            elif record.completion_date:
                new_status = Student.EnrollStatus.COMPLETE
            else:
                continue
            student.enroll_status = new_status
            student.save(update_fields=['enroll_status'])
            status_changed += 1
            self.stdout.write(f'{student.get_full_name()}: active → {new_status}')
            logger.info('Updated %s enroll_status to %s', student, new_status)

        self.stdout.write(self.style.SUCCESS(
            f'Done. Archived {archived_count} course(s), updated {status_changed} student status(es).'
        ))
