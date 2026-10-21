from django.core import mail
from django.test import TestCase
from django.urls import reverse

from courses.models import Course
from staff.models import StudentInvitation
from students.models import Student

from .models import InstructorCourseAssignment


def _course(n, tag):
    return Course.objects.create(option_number=n, tag=tag, name=f'{tag} Course', price=1000, min_down=100)


class InstructorInviteStudentTests(TestCase):
    def setUp(self):
        self.emt  = _course(1, 'EMT')
        self.aemt = _course(2, 'AEMT')
        self.instructor = Student.objects.create_user('inst', password='x', role=Student.Role.INSTRUCTOR)
        InstructorCourseAssignment.objects.create(instructor=self.instructor, course=self.emt, role='primary')
        self.client.force_login(self.instructor)

    def test_invite_pins_course_and_sends_email(self):
        resp = self.client.post(reverse('instructor_invite_student', args=[self.emt.pk]), {'email': 'New@Example.com'})
        self.assertRedirects(resp, reverse('instructor_course_detail', args=[self.emt.pk]), fetch_redirect_response=False)
        inv = StudentInvitation.objects.get(email='new@example.com')
        self.assertEqual(inv.course, self.emt)
        self.assertEqual(inv.created_by, self.instructor)
        self.assertEqual(len(mail.outbox), 1)

    def test_cannot_invite_to_unassigned_course(self):
        resp = self.client.post(reverse('instructor_invite_student', args=[self.aemt.pk]), {'email': 'x@example.com'})
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(StudentInvitation.objects.exists())

    def test_rejects_existing_account_email(self):
        Student.objects.create_user('stu', email='taken@example.com', password='x')
        self.client.post(reverse('instructor_invite_student', args=[self.emt.pk]), {'email': 'taken@example.com'})
        self.assertFalse(StudentInvitation.objects.exists())

    def test_resend_only_for_own_course(self):
        inv = StudentInvitation.objects.create(email='a@example.com', course=self.emt)
        other = StudentInvitation.objects.create(email='b@example.com', course=self.aemt)
        self.client.post(reverse('instructor_resend_student_invite', args=[self.emt.pk, inv.pk]))
        self.assertEqual(len(mail.outbox), 1)
        resp = self.client.post(reverse('instructor_resend_student_invite', args=[self.emt.pk, other.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_course_detail_shows_invite_form(self):
        resp = self.client.get(reverse('instructor_course_detail', args=[self.emt.pk]))
        self.assertContains(resp, 'Send Invite')
