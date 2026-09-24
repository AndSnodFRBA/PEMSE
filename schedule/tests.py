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


class CalendarCopyTests(TestCase):
    def setUp(self):
        from .calendar_copy import plan_copy, apply_copy
        self.plan_copy, self.apply_copy = plan_copy, apply_copy
        self.old = _course(1, 'EMT')
        self.new = _course(2, 'EMT2')
        # Sunday quiz deadline before the first Monday session — anchor must be the session.
        CalendarEvent.objects.create(course=self.old, title='Quiz 0', event_type='quiz', date=date(2026, 8, 2))
        CalendarEvent.objects.create(course=self.old, title='Week 1', event_type='session', date=date(2026, 8, 3),
                                     all_day=False, start_time=time(18), end_time=time(22), location='Station 1',
                                     description='CH 1-3')
        CalendarEvent.objects.create(course=self.old, title='Final', event_type='exam', date=date(2026, 11, 16))
        self.staff = Student.objects.create_user('staff', password='x', role=Student.Role.STAFF)

    def test_shifts_by_whole_weeks_from_first_session(self):
        plan = self.plan_copy(self.old, self.new, date(2027, 1, 11))  # a Monday
        self.assertFalse(plan.was_snapped)
        new_dates = {p.source.title: p.new_date for p in plan.events}
        self.assertEqual(new_dates['Week 1'], date(2027, 1, 11))
        self.assertEqual(new_dates['Quiz 0'], date(2027, 1, 10))   # still the Sunday before
        self.assertEqual(new_dates['Final'], date(2027, 4, 26))
        for p in plan.events:
            self.assertEqual(p.new_date.weekday(), p.source.date.weekday())

    def test_non_matching_weekday_snaps_to_nearest(self):
        plan = self.plan_copy(self.old, self.new, date(2027, 1, 13))  # Wednesday
        self.assertTrue(plan.was_snapped)
        self.assertEqual(plan.new_start, date(2027, 1, 11))
        plan = self.plan_copy(self.old, self.new, date(2027, 1, 15))  # Friday -> next Monday
        self.assertEqual(plan.new_start, date(2027, 1, 18))

    def test_apply_copies_fields_and_is_idempotent(self):
        plan = self.plan_copy(self.old, self.new, date(2027, 1, 11))
        self.assertEqual(self.apply_copy(plan, self.new, self.staff), 3)
        e = CalendarEvent.objects.get(course=self.new, title='Week 1')
        self.assertEqual((e.start_time, e.end_time, e.location, e.description, e.all_day, e.created_by),
                         (time(18), time(22), 'Station 1', 'CH 1-3', False, self.staff))
        self.assertEqual(CalendarEvent.objects.filter(course=self.old).count(), 3)  # source untouched

        plan = self.plan_copy(self.old, self.new, date(2027, 1, 11))
        self.assertEqual(len(plan.to_create), 0)
        self.assertEqual(self.apply_copy(plan, self.new, self.staff), 0)
        self.assertEqual(CalendarEvent.objects.filter(course=self.new).count(), 3)

    def test_empty_source_returns_none(self):
        self.assertIsNone(self.plan_copy(self.new, self.old, date(2027, 1, 11)))

    def test_staff_view_preview_then_confirm(self):
        self.client.force_login(self.staff)
        url = reverse('staff_calendar_copy')
        data = {'source': self.old.pk, 'target': self.new.pk, 'new_start': '2027-01-11'}

        r = self.client.post(url, {**data, 'action': 'preview'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Mon Jan 11, 2027')
        self.assertFalse(CalendarEvent.objects.filter(course=self.new).exists())

        r = self.client.post(url, {**data, 'action': 'confirm'})
        self.assertRedirects(r, f"{reverse('staff_calendar')}?course={self.new.pk}", fetch_redirect_response=False)
        self.assertEqual(CalendarEvent.objects.filter(course=self.new).count(), 3)

    def test_same_course_rejected(self):
        self.client.force_login(self.staff)
        r = self.client.post(reverse('staff_calendar_copy'),
                             {'source': self.old.pk, 'target': self.old.pk, 'new_start': '2027-01-11', 'action': 'confirm'})
        self.assertContains(r, 'Pick two different courses.')

    def test_students_cannot_use_it(self):
        self.client.force_login(Student.objects.create_user('stu2', password='x'))
        r = self.client.get(reverse('staff_calendar_copy'))
        self.assertEqual(r.status_code, 302)

    def _instructor(self):
        inst = Student.objects.create_user('inst', password='x', role=Student.Role.INSTRUCTOR)
        # Taught the old course last year (assignment now inactive), teaching the new one.
        InstructorCourseAssignment.objects.create(instructor=inst, course=self.old, role='primary', is_active=False)
        InstructorCourseAssignment.objects.create(instructor=inst, course=self.new, role='primary')
        return inst

    def test_instructor_can_copy_from_past_course_to_current_course(self):
        self.client.force_login(self._instructor())
        r = self.client.post(reverse('instructor_calendar_copy'), {
            'source': self.old.pk, 'target': self.new.pk, 'new_start': '2027-01-11', 'action': 'confirm'})
        self.assertRedirects(r, reverse('instructor_calendar'), fetch_redirect_response=False)
        self.assertEqual(CalendarEvent.objects.filter(course=self.new).count(), 3)

    def test_instructor_cannot_target_course_they_do_not_teach(self):
        other = _course(3, 'AEMT')
        self.client.force_login(self._instructor())
        r = self.client.post(reverse('instructor_calendar_copy'), {
            'source': self.old.pk, 'target': other.pk, 'new_start': '2027-01-11', 'action': 'confirm'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(CalendarEvent.objects.filter(course=other).exists())

    def test_instructor_cannot_copy_from_course_they_never_taught(self):
        other = _course(3, 'AEMT')
        CalendarEvent.objects.create(course=other, title='AEMT Week 1', event_type='session', date=date(2026, 8, 3))
        self.client.force_login(self._instructor())
        r = self.client.post(reverse('instructor_calendar_copy'), {
            'source': other.pk, 'target': self.new.pk, 'new_start': '2027-01-11', 'action': 'confirm'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(CalendarEvent.objects.filter(course=self.new).exists())

    def test_instructor_page_uses_instructor_portal(self):
        self.client.force_login(self._instructor())
        r = self.client.get(reverse('instructor_calendar_copy'))
        self.assertContains(r, 'class="inst-topbar"')
        self.assertContains(r, f'href="{reverse("instructor_calendar")}"')
