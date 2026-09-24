from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from courses.models import Course, CourseEnrollment
from instructor.models import InstructorCourseAssignment
from students.models import Student

from .ics import build_calendar
from .models import CalendarEvent


def _course(n, tag, **kw):
    return Course.objects.create(
        option_number=n, tag=tag, name=f'{tag} Course', price=1000, min_down=100, **kw,
    )


class CalendarFeedTests(TestCase):
    def setUp(self):
        self.emt  = _course(1, 'EMT')
        self.aemt = _course(2, 'AEMT')
        CalendarEvent.objects.create(course=self.emt,  title='EMT Airway',  date=date(2026, 10, 5))
        CalendarEvent.objects.create(course=self.aemt, title='AEMT IV Lab', date=date(2026, 10, 6))

        self.student = Student.objects.create_user('stu', password='x')
        CourseEnrollment.objects.create(student=self.student, course=self.emt)

        self.instructor = Student.objects.create_user('inst', password='x', role=Student.Role.INSTRUCTOR)
        InstructorCourseAssignment.objects.create(instructor=self.instructor, course=self.emt,  role='primary')
        InstructorCourseAssignment.objects.create(instructor=self.instructor, course=self.aemt, role='primary')

        self.staff = Student.objects.create_user('staff', password='x', role=Student.Role.STAFF)

    def _get(self, user, course=None):
        if course is None:
            url = reverse('calendar_feed', args=[user.calendar_token])
        else:
            url = reverse('calendar_course_feed', args=[user.calendar_token, course.pk])
        return self.client.get(url)

    def test_course_feed_contains_only_that_course(self):
        for user in (self.instructor, self.staff):
            emt = self._get(user, self.emt).content.decode()
            aemt = self._get(user, self.aemt).content.decode()
            self.assertIn('EMT Airway', emt)
            self.assertNotIn('AEMT IV Lab', emt)
            self.assertIn('AEMT IV Lab', aemt)
            self.assertNotIn('EMT Airway', aemt)
            # Each course feed carries its own calendar name
            self.assertIn('X-WR-CALNAME', emt)
            self.assertIn('EMT: EMT Course', emt.replace('\r\n ', ''))
            self.assertIn('AEMT: AEMT Course', aemt.replace('\r\n ', ''))

    def test_combined_feed_still_has_all_of_users_courses(self):
        body = self._get(self.instructor).content.decode()
        self.assertIn('EMT Airway', body)
        self.assertIn('AEMT IV Lab', body)

    def test_student_cannot_subscribe_to_course_they_are_not_in(self):
        self.assertEqual(self._get(self.student, self.emt).status_code, 200)
        self.assertEqual(self._get(self.student, self.aemt).status_code, 404)

    def test_bad_token_404s(self):
        other = Student.objects.create_user('other', password='x')
        url = reverse('calendar_course_feed', args=[other.calendar_token, self.emt.pk])
        other.delete()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_calendar_pages_list_per_course_links(self):
        cases = [(self.student, 'calendar', [self.emt]),
                 (self.instructor, 'instructor_calendar', [self.emt, self.aemt]),
                 (self.staff, 'staff_calendar', [self.emt, self.aemt])]
        for user, page, courses in cases:
            self.client.force_login(user)
            body = self.client.get(reverse(page)).content.decode()
            for c in courses:
                self.assertIn(reverse('calendar_course_feed', args=[user.calendar_token, c.pk]), body)


class IcsFormatTests(TestCase):
    def test_crlf_description_does_not_leave_bare_cr(self):
        course = _course(1, 'EMT')
        event = CalendarEvent.objects.create(
            course=course, title='Airway', date=date(2026, 10, 5), all_day=False,
            start_time=time(18), end_time=time(22), description='Read ch 1\r\nBring gear',
        )
        ics = build_calendar([event], 'PEMSE')
        self.assertNotIn('\r', ics.replace('\r\n', ''))
        self.assertIn('Read ch 1\\nBring gear', ics)

    def test_long_lines_folded_to_75_octets(self):
        ics = build_calendar([], 'PEMSE — ' + 'Emergency Medical Technician — ' * 5)
        for line in ics.split('\r\n'):
            self.assertLessEqual(len(line.encode('utf-8')), 75)
