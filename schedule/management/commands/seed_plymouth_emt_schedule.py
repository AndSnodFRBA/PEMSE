"""
python manage.py seed_plymouth_emt_schedule [--course-id <id>]

Loads the Plymouth EMT course calendar (Nov 2026 – Feb 2027):
  • Wednesday class sessions (in-person lecture)
  • Tuesday online quiz/exam due dates
  • Holidays / notable dates

Safe to re-run — uses update_or_create keyed on (course, date, event_type, title).

The command finds the Plymouth course by looking for a Course whose
location_city or location_name contains "Plymouth" (case-insensitive).
If more than one matches, pass --course-id to specify exactly which one.
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from courses.models import Course
from schedule.models import CalendarEvent


# ---------------------------------------------------------------------------
# Class sessions (Wednesdays)
# ---------------------------------------------------------------------------
SESSIONS = [
    dict(
        date=date(2026, 11, 11),
        title='Veterans Day / Organizational Meeting / CH 1-3',
        description='Veterans Day. Organizational Meeting. CH 1-3 overview.',
    ),
    dict(
        date=date(2026, 11, 18),
        title='CH 4-6',
        description='CH 4: Communication / Documentation; CH 5: Medical Terminology; CH 6: The Human Body',
    ),
    dict(
        date=date(2026, 11, 24),
        title='CH 7-9',
        description='CH 7: Life Span Development; CH 8: Lifting and Moving; CH 9: Team Approach',
    ),
    dict(
        date=date(2026, 12, 2),
        title='CH 10-11',
        description='CH 10: Patient Assessment; CH 11: Airway Management',
    ),
    dict(
        date=date(2026, 12, 9),
        title='Shock / BLS / Medical Overview',
        description='CH 13: Shock; CH 14: BLS Resuscitation; CH 15: Medical Overview',
    ),
    dict(
        date=date(2026, 12, 16),
        title='CH 16-18',
        description='CH 16: Respiratory Emergencies; CH 17: Cardiovascular Emergencies; CH 18: Neurologic Emergencies',
    ),
    dict(
        date=date(2026, 12, 23),
        title='CH 19-21',
        description='CH 19: GI & Urologic Emergencies; CH 20: Endocrine Emergencies; CH 21: Immunologic Emergencies',
    ),
    dict(
        date=date(2027, 1, 6),
        title='CH 22-24',
        description='CH 22: Toxicology; CH 23: Psychiatric Emergencies; CH 24: Gynecologic Emergencies',
    ),
    dict(
        date=date(2027, 1, 13),
        title='CH 25-27',
        description='CH 25: Trauma Overview; CH 26: Bleeding; CH 27: Soft-Tissue Injuries',
    ),
    dict(
        date=date(2027, 1, 20),
        title='CH 28-30',
        description='CH 28: Face and Neck Injuries; CH 29: Head and Spine Injuries; CH 30: Chest Injuries',
    ),
    dict(
        date=date(2027, 1, 27),
        title='CH 31-32',
        description='CH 31: Abdominal and Genitourinary Injuries; CH 32: Orthopedic Injuries',
    ),
    dict(
        date=date(2027, 2, 3),
        title='CH 33-35',
        description='CH 33: Environmental Emergencies; CH 34: Pediatric Emergencies; CH 35: Geriatric Emergencies',
    ),
    dict(
        date=date(2027, 2, 10),
        title='CH 36-38',
        description='CH 36: Patients with Special Challenges; CH 37: Transport Operations; CH 38: Vehicle Extrication',
    ),
    dict(
        date=date(2027, 2, 17),
        title='CH 39-41 / FISDAP or other pretests open',
        description='CH 39-41. FISDAP or other pretest exams open.',
    ),
    dict(
        date=date(2027, 2, 24),
        title='Final Written Exam + Skills Lab',
        description='Final written exam and skills lab.',
    ),
]

# ---------------------------------------------------------------------------
# Online quiz / exam due dates (Tuesdays) and holidays
# ---------------------------------------------------------------------------
DEADLINES = [
    # Nov 2026
    dict(date=date(2026, 11, 17), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 1-3 due online'),
    dict(date=date(2026, 11, 26), event_type=CalendarEvent.EventType.OTHER,
         title='Thanksgiving Day', description='Thanksgiving Day — no class'),

    # Dec 2026
    dict(date=date(2026, 12, 1), event_type=CalendarEvent.EventType.QUIZ,
         title='CH 4-6 Quizzes due online'),
    dict(date=date(2026, 12, 8), event_type=CalendarEvent.EventType.EXAM,
         title='Section 1 Exam CH 1-9 due online'),
    dict(date=date(2026, 12, 8), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 7-9 due online'),
    dict(date=date(2026, 12, 15), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 10-11 due online'),
    dict(date=date(2026, 12, 15), event_type=CalendarEvent.EventType.EXAM,
         title='CH 10 Exam due online'),
    dict(date=date(2026, 12, 22), event_type=CalendarEvent.EventType.EXAM,
         title='Exam 11 & 12 due online'),
    dict(date=date(2026, 12, 22), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 14-16 due online'),
    dict(date=date(2026, 12, 24), event_type=CalendarEvent.EventType.OTHER,
         title='Christmas Eve'),
    dict(date=date(2026, 12, 25), event_type=CalendarEvent.EventType.OTHER,
         title='Christmas Day'),
    dict(date=date(2026, 12, 31), event_type=CalendarEvent.EventType.OTHER,
         title="New Year's Eve"),

    # Jan 2027
    dict(date=date(2027, 1, 1), event_type=CalendarEvent.EventType.OTHER,
         title="New Year's Day"),
    dict(date=date(2027, 1, 5), event_type=CalendarEvent.EventType.EXAM,
         title='Section 5 Exam due online'),
    dict(date=date(2027, 1, 5), event_type=CalendarEvent.EventType.EXAM,
         title='Section 6A Exam due online'),
    dict(date=date(2027, 1, 5), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 17-19 due online'),
    dict(date=date(2027, 1, 12), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 20-22 due online'),
    dict(date=date(2027, 1, 18), event_type=CalendarEvent.EventType.OTHER,
         title='Martin Luther King Day'),
    dict(date=date(2027, 1, 19), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 23-25 due online'),
    dict(date=date(2027, 1, 19), event_type=CalendarEvent.EventType.EXAM,
         title='Section 6B Exam CH 20-24 due online'),
    dict(date=date(2027, 1, 26), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 26-28 due online'),

    # Feb 2027
    dict(date=date(2027, 2, 2), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 29-31 due online'),
    dict(date=date(2027, 2, 2), event_type=CalendarEvent.EventType.EXAM,
         title='Section 7A Exam due online'),
    dict(date=date(2027, 2, 9), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 32-33 due online'),
    dict(date=date(2027, 2, 9), event_type=CalendarEvent.EventType.EXAM,
         title='Section 7B Exam due online'),
    dict(date=date(2027, 2, 14), event_type=CalendarEvent.EventType.OTHER,
         title="Valentine's Day"),
    dict(date=date(2027, 2, 15), event_type=CalendarEvent.EventType.OTHER,
         title="Presidents' Day"),
    dict(date=date(2027, 2, 16), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 34-36 due online'),
    dict(date=date(2027, 2, 23), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 37-42 due online'),
    dict(date=date(2027, 2, 23), event_type=CalendarEvent.EventType.EXAM,
         title='Sections 8 & 9 Exams due online'),

    # Mar 2027
    dict(date=date(2027, 3, 17), event_type=CalendarEvent.EventType.OTHER,
         title="St. Patrick's Day"),
]


class Command(BaseCommand):
    help = 'Seed the Plymouth EMT course calendar (Nov 2026 – Feb 2027)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--course-id',
            type=int,
            default=None,
            help='PK of the Plymouth EMT course (required only if auto-detection finds multiple matches)',
        )

    def handle(self, *args, **options):
        course_id = options['course_id']

        if course_id:
            try:
                courses = [Course.objects.get(pk=course_id)]
            except Course.DoesNotExist:
                raise CommandError(f'No course found with pk={course_id}')
        else:
            # Auto-detect by location
            from django.db.models import Q
            courses = list(Course.objects.filter(
                Q(location_city__icontains='plymouth') |
                Q(location_name__icontains='plymouth') |
                Q(name__icontains='plymouth')
            ))
            if not courses:
                raise CommandError(
                    'No course found with "Plymouth" in location_city, location_name, or name. '
                    'Pass --course-id <pk> to specify the course manually.'
                )
            if len(courses) > 1:
                self.stderr.write('Multiple Plymouth courses found:')
                for c in courses:
                    self.stderr.write(f'  pk={c.pk}  Option {c.option_number} — {c.name}')
                raise CommandError('Pass --course-id <pk> to specify which one to seed.')

        course = courses[0]
        self.stdout.write(f'Seeding calendar for: pk={course.pk}  Option {course.option_number} — {course.name}')

        session_count = 0
        for s in SESSIONS:
            CalendarEvent.objects.update_or_create(
                course=course,
                date=s['date'],
                event_type=CalendarEvent.EventType.SESSION,
                title=s['title'],
                defaults=dict(
                    description=s.get('description', ''),
                    all_day=True,
                    start_time=None,
                    end_time=None,
                    location='',
                ),
            )
            session_count += 1

        deadline_count = 0
        for d in DEADLINES:
            CalendarEvent.objects.update_or_create(
                course=course,
                date=d['date'],
                event_type=d['event_type'],
                title=d['title'],
                defaults=dict(
                    description=d.get('description', ''),
                    all_day=True,
                    start_time=None,
                    end_time=None,
                    location='',
                ),
            )
            deadline_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done — {session_count} class sessions + {deadline_count} deadlines/holidays seeded.'
        ))
