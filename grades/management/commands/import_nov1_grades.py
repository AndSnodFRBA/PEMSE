"""
Management command: import grades from the Nov 1 PEMSE spreadsheet.

Usage (Railway console or local):
    python manage.py import_nov1_grades [--dry-run] [--force]

--dry-run : print what would happen without saving anything
--force   : re-import even if grades already exist (overwrites scores)
"""

from django.core.management.base import BaseCommand
from django.db import transaction

NC = None

COLUMN_MAP = [
    ('quiz',  1),  ('quiz',  2),  ('quiz',  3),  ('quiz',  4),  ('quiz',  5),
    ('quiz',  6),  ('quiz',  7),  ('quiz',  8),  ('quiz',  9),
    ('exam',  1),
    ('quiz', 10),
    ('exam',  2),
    ('quiz', 11),
    ('exam',  3),
    ('quiz', 12),
    ('exam',  4),
    ('quiz', 13), ('quiz', 14),
    ('exam',  5),
    ('quiz', 15), ('quiz', 16), ('quiz', 17), ('quiz', 18), ('quiz', 19),
    ('exam', 61),
    ('quiz', 20), ('quiz', 21), ('quiz', 22), ('quiz', 23), ('quiz', 24),
    ('exam', 62),
    ('quiz', 25), ('quiz', 26), ('quiz', 27), ('quiz', 28), ('quiz', 29),
    ('exam', 71),
    ('quiz', 30), ('quiz', 31), ('quiz', 32), ('quiz', 33),
    ('exam', 72),
    ('quiz', 34), ('quiz', 35), ('quiz', 36), ('quiz', 37),
    ('exam',  8),
]

EXAM_LABELS = {
    1: 'Section Exam 1',  2: 'Section Exam 2',  3: 'Section Exam 3',
    4: 'Section Exam 4',  5: 'Section Exam 5',
    61: 'Section Exam 6A', 62: 'Section Exam 6B',
    71: 'Section Exam 7A', 72: 'Section Exam 7B',
    8: 'Section Exam 8',   9: 'Section Exam 9',
}

IMPORT_DATA = {
    "westonbd99@hotmail.com": [
        84,100,96,76,88,86,84,80,80, 87,
        76, 88,
        82, 82,
        NC, 82,
        NC, 68, 74, 88,
        84,88,96,84, NC,
        88,92,88,84,96, NC,
        100,76,80,96,84, NC,
        96,100,84,88, NC,
        NC,NC,NC,NC, NC,
    ],
    "logannoah215@gmail.com": [
        58,74,44,70,84,67,88,84,86, 81,
        96, 95,
        96, 64,
        92, 96,
        100,96,96, 100,
        100,100,100,96, 99,
        100,100,100,100,96, 98,
        96,100,96,96,96, 99,
        100,96,100,96, 94,
        96,92,96,100, NC,
    ],
    "tkinser1226@gmail.com": [
        52,NC,NC,NC,NC,NC,NC,NC,NC, NC,
        NC, NC,
        NC, NC,
        NC, NC,
        NC,NC, NC,
        NC,NC,NC,NC,NC, NC,
        NC,NC,NC,NC,NC, NC,
        NC,NC,NC,NC,NC, NC,
        NC,NC,NC,NC, NC,
        NC,NC,NC,NC, NC,
    ],
    "irenelheureux23@gmail.com": [
        96,96,100,100,100,100,100,100,100, 98,
        98, 95,
        100, 94,
        96, 100,
        92,92, 92,
        100,100,96,100,100, 97,
        96,100,100,100,100, 96,
        96,92,92,92,96, 94,
        92,100,96,84, NC,
        92,96, NC,NC, NC,
    ],
    "ryleepackett2007@gmail.com": [
        72,74,92,76,100,100,84,100,96, 89,
        98, 80,
        82, 87,
        68, 82,
        72,88, 92,
        84,80,74,76,86, 85,
        72,88,76,92,88, 90,
        70,84,74,86,84, 84,
        80,80,76,84, 85,
        84,76,NC,NC, NC,
    ],
    "genericcuserr@gmail.com": [
        76,82,80,NC,NC,NC,NC,NC,NC, NC,
        NC, NC,
        NC, NC,
        NC, NC,
        NC,NC, NC,
        NC,NC,NC,NC,NC, NC,
        NC,NC,NC,NC,NC, NC,
        NC,NC,NC,NC,NC, NC,
        NC,NC,NC,NC, NC,
        NC,NC,NC,NC, NC,
    ],
    "brandidawnreimers@gmail.com": [
        84,88,84,96,84,90,96,94,94, 94,
        94, NC,
        90, NC,
        96, NC,
        98,96, NC,
        98,92,88,96,96, NC,
        84,100,92,96,100, NC,
        100,96,100,92,NC, NC,
        NC,NC,NC,NC, NC,
        NC,NC,NC,NC, NC,
    ],
    "nebraskacitygenetics01@gmail.com": [
        80,76,70,76,92,88,NC,70,76, 82,
        62, 57,
        NC, NC,
        NC, NC,
        NC,NC, NC,
        NC,NC,NC,NC,NC, NC,
        NC,NC,NC,NC,NC, NC,
        NC,NC,NC,NC,NC, NC,
        NC,NC,NC,NC, NC,
        NC,NC,NC,NC, NC,
    ],
    "claytonsalberg@gmail.com": [
        76,76,92,84,100,98,92,90,100, 97,
        92, 97,
        98, 92,
        92, 95,
        90,92, 96,
        92,92,92,92,96, 96,
        92,100,92,96,96, 98,
        96,100,100,88,96, 96,
        96,96,88,88, 97,
        84,100,96,92, NC,
    ],
    "michalakkatie@yahoo.com": [
        86,92,90,96,96,94,92,92,100, 97,
        94, 94,
        90, 87,
        92, 93,
        96,96, 92,
        96,92,88,88,96, 88,
        92,100,100,92,92, 96,
        96,96,100,96,84, 94,
        84,92,92,88, 94,
        88,NC,88,NC, NC,
    ],
    "wsct22@outlook.com": [
        82,100,92,92,96,96,96,88,92, 91,
        96, 96,
        96, 94,
        96, 98,
        96,88, 93,
        96,96,98,100,92, 93,
        96,96,88,88,NC, NC,
        100,96,NC,NC,NC, NC,
        NC,NC,NC,NC, NC,
        NC,NC,NC,NC, NC,
    ],
}


class Command(BaseCommand):
    help = 'Import Nov 1 grade spreadsheet data into gradebooks'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print actions without saving')
        parser.add_argument('--force', action='store_true', help='Overwrite existing grades')

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        from grades.models import GradeBook, QuizGrade, SectionExamGrade
        from courses.models import CourseEnrollment
        from collections import Counter

        User = get_user_model()
        dry = options['dry_run']
        force = options['force']

        if dry:
            self.stdout.write(self.style.WARNING('DRY RUN — nothing will be saved'))

        # 1. Match emails → users
        user_map = {}
        for email in IMPORT_DATA:
            u = User.objects.filter(email__iexact=email).first()
            if u:
                user_map[email] = u
                self.stdout.write(f'  FOUND   {email} → {u.get_full_name()} (pk={u.pk})')
            else:
                self.stdout.write(self.style.WARNING(f'  MISSING {email}'))

        if not user_map:
            self.stdout.write(self.style.ERROR('No matching users — aborting.'))
            return

        # 2. Find best course
        counter = Counter()
        for u in user_map.values():
            for enr in CourseEnrollment.objects.filter(student=u):
                counter[enr.course_id] += 1

        if not counter:
            self.stdout.write(self.style.ERROR('No enrollments found — aborting.'))
            return

        from courses.models import Course
        best_id, match_count = counter.most_common(1)[0]
        course = Course.objects.get(pk=best_id)
        self.stdout.write(self.style.SUCCESS(
            f'\nTargeting course [{best_id}] "{course.name}" ({match_count}/{len(user_map)} students matched)'
        ))

        # 3. Show all courses with counts for debugging
        self.stdout.write('\nAll courses with enrolled students from this list:')
        for cid, cnt in counter.most_common():
            c = Course.objects.get(pk=cid)
            self.stdout.write(f'  pk={cid} "{c.name}" — {cnt} student(s)')

        # 4. Import
        imported = nc = skipped = 0

        with transaction.atomic():
            for email, values in IMPORT_DATA.items():
                user = user_map.get(email)
                if not user:
                    continue

                gb, created = GradeBook.objects.get_or_create(student=user, course=course)
                if gb.is_finalized:
                    self.stdout.write(self.style.WARNING(f'  SKIP (finalized)  {user.get_full_name()}'))
                    skipped += 1
                    continue

                student_imported = student_nc = 0
                for i, raw_val in enumerate(values):
                    if i >= len(COLUMN_MAP):
                        break
                    kind, number = COLUMN_MAP[i]
                    score = None if raw_val is None else float(raw_val)
                    is_nc = score is None
                    status = 'not_completed' if is_nc else 'completed'

                    if not dry:
                        if kind == 'quiz':
                            obj, created_grade = QuizGrade.objects.get_or_create(
                                gradebook=gb, quiz_number=number,
                                defaults={'quiz_name': f'Quiz {number}', 'score': score, 'status': status},
                            )
                            if not created_grade and force:
                                obj.score = score
                                obj.status = status
                                obj.save()
                        else:
                            obj = SectionExamGrade.objects.filter(
                                gradebook=gb, exam_number=number, is_final_exam=False,
                            ).first()
                            if obj and force:
                                obj.score = score
                                obj.status = status
                                obj.save()
                            elif not obj:
                                SectionExamGrade.objects.create(
                                    gradebook=gb,
                                    exam_number=number,
                                    exam_name=EXAM_LABELS.get(number, f'Section Exam {number}'),
                                    is_final_exam=False,
                                    score=score,
                                    status=status,
                                )

                    student_imported += 1
                    if is_nc:
                        student_nc += 1

                imported += student_imported
                nc += student_nc
                label = 'NC ' if dry else ('NEW' if created else 'UPD')
                self.stdout.write(
                    f'  {label}  {user.get_full_name()} <{email}> '
                    f'— {student_imported - student_nc} scored, {student_nc} NC'
                )

            if dry:
                raise Exception('DRY RUN — rolling back')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone — {imported} grade records ({nc} NC), {skipped} student(s) skipped.'
        ))
