"""
python manage.py import_grades_from_xlsx <xlsx_path> [--course-id <id>] [--dry-run]

Imports quiz scores, section exam scores, and worksheet scores from an
exported gradebook XLSX (the format used by the Nebraska City EMT course
LMS export) into the PEMSE GradeBook.

The command:
  - Matches students by email address
  - Creates GradeBook if one doesn't exist yet for (student, course)
  - Uses update_or_create for each QuizGrade, SectionExamGrade, WorksheetGrade
  - Skips '-' (not completed / no entry) values gracefully
  - Prints a summary of created / updated / skipped records
  - Does nothing with --dry-run (shows what it would do)

Course auto-detection: looks for a Course with location_city or
location_name containing "Nebraska City". Pass --course-id if
multiple courses match.
"""
import sys
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

XLSX_PATH_HELP = 'Path to the exported XLSX gradebook file'


# ---------------------------------------------------------------------------
# Column mapping (0-indexed, skipping the header row)
# ---------------------------------------------------------------------------
# (col_index, quiz_number)  — Chapter Quizzes
QUIZ_COLUMNS = [
    (3,  1), (4,  2), (5,  3), (6,  4), (7,  5), (8,  6),
    (9,  7), (10, 8), (11, 9),
    (13, 10),                   # Ch 10 Quiz
    (15, 11),                   # Ch 11 Quiz
    (17, 12),                   # Ch 12 Quiz
    (19, 13), (20, 14),         # Ch 13, Ch 14 Quizzes
    (22, 15), (23, 16), (24, 17), (25, 18), (26, 19),  # Ch 15-19
    (28, 20), (29, 21), (30, 22), (31, 23), (32, 24),  # Ch 20-24
    (34, 25), (35, 26), (36, 27), (37, 28), (38, 29),  # Ch 25-29
    (40, 30), (41, 31), (42, 32), (43, 33),             # Ch 30-33
    (45, 34), (46, 35), (47, 36), (48, 37),             # Ch 34-37
    (50, 38), (51, 39), (52, 40), (53, 41),             # Ch 38-41
]

# (col_index, exam_number, exam_name, is_final)
EXAM_COLUMNS = [
    (12,  1, 'Section Exam 1: CH 1-9',    False),
    (14,  2, 'Section Exam 2: CH 10',     False),
    (16,  3, 'Section Exam 3: CH 11',     False),
    (18,  4, 'Section Exam 4: CH 12',     False),
    (21,  5, 'Section 5 Exam: CH 13 & 14', False),
    (27,  6, 'Section 6A Exam: CH 15-19', False),
    (33,  7, 'Section 6B Exam: CH 20-24', False),
    (39,  8, 'Section 7A Exam: CH 25-29', False),
    (44,  9, 'Section 7B Exam: CH 30-33', False),
    (49, 10, 'Section 8 Exam: CH 34-37',  False),
    (54, 11, 'Section 9 Exam: CH 38-41',  False),
    (97, None, 'Final Written Exam',       True),
]

# (col_index, assignment_name) — Worksheets / interactive lectures
WORKSHEET_COLUMNS = [
    (55, 'Soft-Skill Simulations'),
] + [
    (56 + i, f'Interactive Lecture: Chapter {i + 1}')
    for i in range(41)   # Columns 56-96 → Ch 1-41
]


def _parse_score(val):
    """Return Decimal score or None. '-' and None → None."""
    if val is None or val == '-' or val == '':
        return None
    try:
        return Decimal(str(val))
    except Exception:
        return None


class Command(BaseCommand):
    help = 'Import grades from an XLSX export into the PEMSE gradebook'

    def add_arguments(self, parser):
        parser.add_argument('xlsx_path', help=XLSX_PATH_HELP)
        parser.add_argument('--course-id', type=int, default=None,
                            help='PK of the course (auto-detect by location if omitted)')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would change without writing anything')

    def handle(self, *args, **options):
        import openpyxl
        from courses.models import Course
        from grades.models import GradeBook, QuizGrade, SectionExamGrade, WorksheetGrade
        from students.models import Student

        xlsx_path = options['xlsx_path']
        dry_run   = options['dry_run']

        # ---- resolve course ----
        course_id = options['course_id']
        if course_id:
            try:
                course = Course.objects.get(pk=course_id)
            except Course.DoesNotExist:
                raise CommandError(f'No course with pk={course_id}')
        else:
            from django.db.models import Q
            candidates = list(Course.objects.filter(
                Q(location_city__icontains='nebraska city') |
                Q(location_name__icontains='nebraska city') |
                Q(name__icontains='nebraska city')
            ))
            if not candidates:
                raise CommandError(
                    'No course found with "Nebraska City" in location. '
                    'Pass --course-id <pk> to specify the course.'
                )
            if len(candidates) > 1:
                self.stderr.write('Multiple Nebraska City courses found:')
                for c in candidates:
                    self.stderr.write(f'  pk={c.pk}  Option {c.option_number} — {c.name}')
                raise CommandError('Pass --course-id <pk> to specify which one.')
            course = candidates[0]

        self.stdout.write(f'Course: pk={course.pk}  Option {course.option_number} — {course.name}')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be saved'))

        # ---- load workbook ----
        try:
            wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        except FileNotFoundError:
            raise CommandError(f'File not found: {xlsx_path}')
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise CommandError('Spreadsheet appears empty')

        header = rows[0]
        data_rows = [r for r in rows[1:] if any(v is not None for v in r)]

        self.stdout.write(f'Found {len(data_rows)} student rows')

        totals = dict(students_matched=0, students_skipped=0,
                      quizzes_created=0, quizzes_updated=0,
                      exams_created=0, exams_updated=0,
                      worksheets_created=0, worksheets_updated=0)

        for row in data_rows:
            email = row[1]
            if not email:
                continue
            email = str(email).strip()

            # name is prefixed with 2-char initials (e.g. "WDWeston Doty")
            raw_name = str(row[0]).strip() if row[0] else ''
            display_name = raw_name[2:] if len(raw_name) > 2 else raw_name

            try:
                student = Student.objects.get(email__iexact=email)
            except Student.DoesNotExist:
                self.stderr.write(f'  SKIP — no student with email {email} ({display_name})')
                totals['students_skipped'] += 1
                continue
            except Student.MultipleObjectsReturned:
                self.stderr.write(f'  SKIP — multiple students with email {email}')
                totals['students_skipped'] += 1
                continue

            totals['students_matched'] += 1
            self.stdout.write(f'  Processing {display_name} ({email})')

            with transaction.atomic():
                if not dry_run:
                    gb, _ = GradeBook.objects.get_or_create(student=student, course=course)
                else:
                    try:
                        gb = GradeBook.objects.get(student=student, course=course)
                    except GradeBook.DoesNotExist:
                        gb = None  # dry-run: can't create records without a gb

                # ---- quizzes ----
                for col_idx, quiz_num in QUIZ_COLUMNS:
                    if col_idx >= len(row):
                        continue
                    score = _parse_score(row[col_idx])
                    if score is None:
                        continue
                    quiz_name = f'Chapter {quiz_num} Quiz'
                    if not dry_run and gb:
                        obj, created = QuizGrade.objects.update_or_create(
                            gradebook=gb,
                            quiz_number=quiz_num,
                            defaults=dict(
                                quiz_name=quiz_name,
                                score=score,
                                status=QuizGrade.Status.COMPLETED,
                            ),
                        )
                        if created:
                            totals['quizzes_created'] += 1
                        else:
                            totals['quizzes_updated'] += 1
                    else:
                        self.stdout.write(f'    [DRY] Quiz {quiz_num}: {score}')

                # ---- section exams ----
                for col_idx, exam_num, exam_name, is_final in EXAM_COLUMNS:
                    if col_idx >= len(row):
                        continue
                    score = _parse_score(row[col_idx])
                    if score is None:
                        continue
                    if not dry_run and gb:
                        lookup = dict(gradebook=gb, is_final_exam=is_final)
                        if not is_final:
                            lookup['exam_number'] = exam_num
                        obj, created = SectionExamGrade.objects.update_or_create(
                            **lookup,
                            defaults=dict(
                                exam_name=exam_name,
                                score=score,
                                status=SectionExamGrade.Status.COMPLETED,
                            ),
                        )
                        if created:
                            totals['exams_created'] += 1
                        else:
                            totals['exams_updated'] += 1
                    else:
                        label = 'Final Exam' if is_final else f'Exam {exam_num}'
                        self.stdout.write(f'    [DRY] {label}: {score}')

                # ---- worksheets ----
                for col_idx, assignment_name in WORKSHEET_COLUMNS:
                    if col_idx >= len(row):
                        continue
                    score = _parse_score(row[col_idx])
                    if score is None:
                        continue
                    if not dry_run and gb:
                        obj, created = WorksheetGrade.objects.update_or_create(
                            gradebook=gb,
                            assignment_name=assignment_name,
                            defaults=dict(score=score),
                        )
                        if created:
                            totals['worksheets_created'] += 1
                        else:
                            totals['worksheets_updated'] += 1
                    else:
                        self.stdout.write(f'    [DRY] Worksheet "{assignment_name}": {score}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done — {totals["students_matched"]} students matched, '
            f'{totals["students_skipped"]} skipped\n'
            f'Quizzes:    {totals["quizzes_created"]} created, {totals["quizzes_updated"]} updated\n'
            f'Exams:      {totals["exams_created"]} created, {totals["exams_updated"]} updated\n'
            f'Worksheets: {totals["worksheets_created"]} created, {totals["worksheets_updated"]} updated'
        ))
