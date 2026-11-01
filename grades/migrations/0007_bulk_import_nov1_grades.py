"""
Data migration — import grades from PEMSE_NC_Grades_11-1.xlsx
Uploaded 2026-11-01 by Andrew Snodgrass (PEMSE staff).

Matches students by email address.
Scores are entered for the single active course (most-recently-created course
that has enrolled students matching these emails).
Columns map as:
  Quiz 1–37  →  QuizGrade.quiz_number 1–37
  Section Exam 1 → exam_number 1
  Section Exam 2 → exam_number 2
  Section Exam 3 → exam_number 3
  Section Exam 4 → exam_number 4
  Section Exam 5 → exam_number 5
  Section Exam 6A → exam_number 61
  Section Exam 6B → exam_number 62
  Section Exam 7A → exam_number 71
  Section Exam 7B → exam_number 72
  Section Exam 8  → exam_number 8
'-' values are set as NOT_COMPLETED (NC).
"""

from django.db import migrations


# ── Raw import data ──────────────────────────────────────────────────────────
# Each entry: (email, [(kind, number, score_or_None), ...])
# kind: 'quiz' or 'exam'
# score: numeric or None (None = NC)

NC = None  # sentinel for not-completed

COLUMN_MAP = [
    # (kind, number)
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

def _v(raw):
    """Convert raw value to float or NC."""
    if raw is None or raw == '-' or raw == '':
        return NC
    try:
        return float(raw)
    except (ValueError, TypeError):
        return NC

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


def import_grades(apps, schema_editor):
    User = apps.get_model('students', 'Student')
    GradeBook = apps.get_model('grades', 'GradeBook')
    QuizGrade = apps.get_model('grades', 'QuizGrade')
    SectionExamGrade = apps.get_model('grades', 'SectionExamGrade')
    CourseEnrollment = apps.get_model('courses', 'CourseEnrollment')
    Course = apps.get_model('courses', 'Course')

    # Find the course these students are enrolled in — pick the one with
    # the most matching enrolled students.
    email_list = list(IMPORT_DATA.keys())
    user_map = {}
    for email in email_list:
        u = User.objects.filter(email__iexact=email).first()
        if u:
            user_map[email] = u

    if not user_map:
        print("  [import] No matching users found — skipping import.")
        return

    # Find the best course
    from collections import Counter
    course_counter = Counter()
    for u in user_map.values():
        for enr in CourseEnrollment.objects.filter(student_id=u.pk):
            course_counter[enr.course_id] += 1

    if not course_counter:
        print("  [import] No enrollments found — skipping import.")
        return

    best_course_id, match_count = course_counter.most_common(1)[0]
    course = Course.objects.get(pk=best_course_id)
    print(f"  [import] Targeting course [{best_course_id}] {course.name} ({match_count} student matches)")

    imported_count = 0
    nc_count = 0

    for email, values in IMPORT_DATA.items():
        user = user_map.get(email)
        if not user:
            print(f"  [import] SKIP — user not found: {email}")
            continue

        gb, _ = GradeBook.objects.get_or_create(
            student_id=user.pk, course_id=best_course_id,
        )
        if gb.is_finalized:
            print(f"  [import] SKIP — gradebook finalized: {user.get_full_name()}")
            continue

        for i, raw_val in enumerate(values):
            if i >= len(COLUMN_MAP):
                break
            kind, number = COLUMN_MAP[i]
            score = _v(raw_val)
            is_nc = (score is None)
            status = 'not_completed' if is_nc else 'completed'

            if kind == 'quiz':
                obj, created = QuizGrade.objects.get_or_create(
                    gradebook=gb,
                    quiz_number=number,
                    defaults={
                        'quiz_name': f'Quiz {number}',
                        'score': score,
                        'status': status,
                    },
                )
                if not created:
                    obj.score = score
                    obj.status = status
                    obj.save()
            else:
                # exam
                obj = SectionExamGrade.objects.filter(
                    gradebook=gb, exam_number=number, is_final_exam=False,
                ).first()
                if obj:
                    obj.score = score
                    obj.status = status
                    obj.save()
                else:
                    SectionExamGrade.objects.create(
                        gradebook=gb,
                        exam_number=number,
                        exam_name=EXAM_LABELS.get(number, f'Section Exam {number}'),
                        is_final_exam=False,
                        score=score,
                        status=status,
                    )

            imported_count += 1
            if is_nc:
                nc_count += 1

        print(f"  [import] OK  {user.get_full_name()} <{email}>")

    print(f"  [import] Done — {imported_count} grade records, {nc_count} marked NC.")


def reverse_import(apps, schema_editor):
    # Non-destructive reverse: just print a notice.
    print("  [import] Reverse not implemented — grades left in place.")


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0006_bulk_import_nov1_grades'),
    ]

    operations = [
        migrations.RunPython(import_grades, reverse_import),
    ]
