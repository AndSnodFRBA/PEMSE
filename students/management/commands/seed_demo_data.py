import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Seed demo instance with realistic fictional sample data'

    def handle(self, *args, **kwargs):
        from django.conf import settings
        if not settings.DEMO_MODE:
            self.stderr.write(self.style.ERROR(
                'This command only runs when DEMO_MODE=True. Refusing to seed.'
            ))
            return

        from students.models import Student, PaymentHistory, PaymentRecord
        from courses.models import Course, CourseEnrollment
        from grades.models import GradeBook, QuizGrade, SectionExamGrade
        from instructor.models import InstructorCourseAssignment, AttendanceRecord, StudentAttendance

        # ── Demo agency staff ──────────────────────────────────────────────
        staff, _ = Student.objects.get_or_create(
            email='director@emstrainingportal.com',
            defaults={
                'username': 'director@emstrainingportal.com',
                'first_name': 'Demo',
                'last_name': 'Director',
                'role': 'staff',
                'is_staff': True,
                'is_active': True,
            }
        )
        staff.set_password('demo1234')
        staff.save()
        self.stdout.write('Created staff: director@emstrainingportal.com / demo1234')

        # ── Demo instructor ────────────────────────────────────────────────
        instructor, _ = Student.objects.get_or_create(
            email='instructor@emstrainingportal.com',
            defaults={
                'username': 'instructor@emstrainingportal.com',
                'first_name': 'Demo',
                'last_name': 'Instructor',
                'role': 'instructor',
                'instructor_license_number': 'NE-EMT-12345',
                'instructor_license_level': 'EMT',
                'instructor_license_expiry': date(2027, 6, 30),
                'is_active': True,
            }
        )
        instructor.set_password('demo1234')
        instructor.save()
        self.stdout.write('Created instructor: instructor@emstrainingportal.com / demo1234')

        # ── Get the EMT course ─────────────────────────────────────────────
        course = Course.objects.filter(is_active=True).first()
        if not course:
            self.stderr.write('No active course found. Run seed_courses first.')
            return

        # Assign instructor to course
        InstructorCourseAssignment.objects.get_or_create(
            instructor=instructor,
            course=course,
            role='primary',
            defaults={'assigned_by': staff, 'is_active': True}
        )

        # ── Demo students ──────────────────────────────────────────────────
        demo_students = [
            ('James', 'Anderson', 'james.anderson@emstrainingportal.com', 92, 'active'),
            ('Maria', 'Rodriguez', 'maria.rodriguez@emstrainingportal.com', 87, 'active'),
            ('Tyler', 'Johnson', 'tyler.johnson@emstrainingportal.com', 78, 'active'),
            ('Sarah', 'Williams', 'sarah.williams@emstrainingportal.com', 95, 'active'),
            ('Michael', 'Brown', 'michael.brown@emstrainingportal.com', 65, 'active'),
            ('Jessica', 'Davis', 'jessica.davis@emstrainingportal.com', 82, 'active'),
            ('Chris', 'Miller', 'chris.miller@emstrainingportal.com', 91, 'active'),
            ('Amanda', 'Wilson', 'amanda.wilson@emstrainingportal.com', 73, 'active'),
        ]

        for first, last, email, grade_level, status in demo_students:
            student, created = Student.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': first,
                    'last_name': last,
                    'role': 'student',
                    'phone': f'308.{random.randint(100,999)}.{random.randint(1000,9999)}',
                    'address': f'{random.randint(100,999)} Main St',
                    'city': random.choice(["Norfolk", "Kearney", "North Platte", "Columbus", "Fremont"]),
                    'state': "NE",
                    'enroll_status': status,
                    'reg_submitted': True,
                    'reg_submitted_at': timezone.now() - timedelta(days=random.randint(10, 30)),
                    'reg_conf_number': f'DEMO-2026-{random.randint(10000,99999)}',
                    'handbook_signed': True,
                    'contract_signed': True,
                    'is_active': True,
                }
            )
            if created:
                student.set_password('demo1234')
                student.save()

            # Enroll in course — this also auto-creates a GradeBook via signal
            enrollment, _ = CourseEnrollment.objects.get_or_create(
                student=student,
                defaults={'course': course}
            )

            # Fetch (or, in the unlikely case the signal didn't run, create) the
            # gradebook and set its participation score to match the demo grade level.
            gb, _ = GradeBook.objects.get_or_create(
                student=student,
                course=course,
                defaults={'participation_score': min(100, grade_level + random.randint(-5, 5))}
            )
            gb.participation_score = min(100, grade_level + random.randint(-5, 5))
            gb.save(update_fields=['participation_score'])

            # Add quiz grades
            for quiz_num in range(1, 10):
                score = min(100, grade_level + random.randint(-8, 8))
                QuizGrade.objects.get_or_create(
                    gradebook=gb,
                    quiz_number=quiz_num,
                    defaults={
                        'quiz_name': f'Quiz {quiz_num}',
                        'score': score,
                        'date_taken': date(2026, 8, 1) + timedelta(weeks=quiz_num),
                    }
                )

            # Add section exam grades
            for exam_num, exam_name in [
                (1, 'Section 1 Exam — CH 1-9'),
                (2, 'Section 2 Exam — CH 10'),
                (3, 'Section 3 Exam — CH 11'),
            ]:
                score = min(100, grade_level + random.randint(-5, 5))
                SectionExamGrade.objects.get_or_create(
                    gradebook=gb,
                    exam_number=exam_num,
                    defaults={
                        'exam_name': exam_name,
                        'score': score,
                        'is_final_exam': False,
                        'date_taken': date(2026, 8, 30) + timedelta(weeks=exam_num),
                    }
                )

            # Add payment history
            PaymentRecord.objects.get_or_create(
                student=student,
                defaults={'method': 'check', 'pay_option': 'schedule'}
            )
            PaymentHistory.objects.get_or_create(
                student=student,
                payment_date=date(2026, 7, 15),
                defaults={
                    'amount': course.min_down,
                    'method': 'check',
                    'check_number': str(random.randint(1000, 9999)),
                    'recorded_by': staff,
                }
            )

            if created:
                self.stdout.write(f'Created student: {email} / demo1234 (grade ~{grade_level}%)')

        # ── Attendance records for first 3 sessions ────────────────────────
        students_list = Student.objects.filter(role='student', email__endswith='@emstrainingportal.com')
        from schedule.models import CalendarEvent
        sessions = CalendarEvent.objects.filter(
            event_type='session',
            course=course
        ).order_by('date')[:3]

        for session_event in sessions:
            att, _ = AttendanceRecord.objects.get_or_create(
                course=course,
                session_date=session_event.date,
                session_type='lecture',
                defaults={
                    'instructor': instructor,
                    'session_topic': session_event.title,
                    'session_start': session_event.start_time,
                    'session_end': session_event.end_time,
                }
            )
            for student in students_list:
                status = 'present' if random.random() > 0.15 else random.choice(['absent', 'late', 'excused'])
                StudentAttendance.objects.get_or_create(
                    session=att,
                    student=student,
                    defaults={'status': status}
                )

        self.stdout.write(self.style.SUCCESS(
            '\nDemo data seeded successfully!'
            '\n\nDemo login credentials:'
            '\n  Staff:      director@emstrainingportal.com / demo1234'
            '\n  Instructor: instructor@emstrainingportal.com / demo1234'
            '\n  Students:   james.anderson@emstrainingportal.com / demo1234 (and 7 others)'
            '\n\nAll student emails follow the pattern: firstname.lastname@emstrainingportal.com'
        ))
