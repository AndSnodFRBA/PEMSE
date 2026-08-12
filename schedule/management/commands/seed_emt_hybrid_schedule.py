"""
python manage.py seed_emt_hybrid_schedule

Loads the Fall 2026 EMT Hybrid / AEMT Hybrid Bridge course calendar:
15 Monday class sessions (lecture + skills lab) and 13 Sunday online
quiz/exam deadlines. Applied to both EMT Hybrid course records (option 3,
with book, and option 4, no book) since students in either attend the
same physical sessions.

Safe to re-run — uses update_or_create keyed on (course, date, event_type, title).
"""
from datetime import date, time

from django.core.management.base import BaseCommand

from courses.models import Course
from schedule.models import CalendarEvent

LOCATION = '709 Rosedale Dr., Scottsbluff, NE 69361'
COURSE_OPTION_NUMBERS = [3, 4]

SESSIONS = [
    dict(date=date(2026, 8, 3), title='Week 1: Organizational Meeting; CH 1-3',
         description='LECTURE: Organizational Meeting; CH 1: EMS Systems; '
                      'CH 2: Workforce Safety & Wellness; CH 3: Medical/Legal\n'
                      'SKILLS: Legal/Ethical; Comm/Documentation'),
    dict(date=date(2026, 8, 10), title='Week 2: CH 4-6',
         description='LECTURE: CH 4: Communication / Documentation; CH 5: Medical Terminology; '
                      'CH 6: The Human Body\n'
                      'SKILLS: Review CH 5-6; Lifting and Moving'),
    dict(date=date(2026, 8, 17), title='Week 3: CH 7-9',
         description='LECTURE: CH 7: Life Span Development; CH 8: Lifting and Moving; '
                      'CH 9: Team Approach\n'
                      'SKILLS: Review CH 7; Human Body'),
    dict(date=date(2026, 8, 24), title='Week 4: CH 10-11',
         description='LECTURE: CH 10: Patient Assessments; CH 11: Airway\n'
                      'SKILLS: Review CH 10; Medical and Trauma Assessments'),
    dict(date=date(2026, 8, 31), title='Week 5: Pharmacology/IV Access (AEMT); Shock/BLS/Medical Overview (EMT)',
         description='LECTURE: AEMT: CH 12 Pharmacology / CH 13 IV Access; '
                      'EMT: CH 13 Shock / CH 14 BLS Resuscitation / CH 15 Medical Overview\n'
                      'SKILLS: Hands On Skills; Patient Assessments; Airway'),
    dict(date=date(2026, 9, 7), title='Week 6: CH 16-18',
         description='LECTURE: CH 16: Respiratory Emergencies; CH 17: Cardiovascular Emergencies; '
                      'CH 18: Neurologic Emergencies\n'
                      'SKILLS: Hands On Skills; IV Access (AEMT); Pharmacology; Review CH 11-12'),
    dict(date=date(2026, 9, 14), title='Week 7: CH 19-21',
         description='LECTURE: CH 19: GI & Urologic Emergencies; CH 20: Endocrine Emergencies; '
                      'CH 21: Immunologic Emergencies\n'
                      'SKILLS: Hands On Skills; CH 16 Respiratory; Medical Skills'),
    dict(date=date(2026, 9, 21), title='Week 8: CH 22-24',
         description='LECTURE: CH 22: Toxicology; CH 23: Psychiatric Emergencies; '
                      'CH 24: Gynecologic Emergencies\n'
                      'SKILLS: Hands On Skills; CH 17 Cardiovascular; Respiratory'),
    dict(date=date(2026, 9, 28), title='Week 9: CH 25-27',
         description='LECTURE: CH 25: Trauma Overview; CH 26: Bleeding; CH 27: Soft-Tissue Injuries\n'
                      'SKILLS: Hands On Skills; CH 18 & 19; Cardiology; Neurologic'),
    dict(date=date(2026, 10, 5), title='Week 10: CH 28-30',
         description='LECTURE: CH 28: Face and Neck Injuries; CH 29: Head and Spine Injuries; '
                      'CH 30: Chest Injuries\n'
                      'SKILLS: Hands On Skills; GI & Urologic; Endocrine / Hematologic'),
    dict(date=date(2026, 10, 12), title='Week 11: CH 31-32',
         description='LECTURE: CH 31: Abdominal and Genitourinary Injuries; CH 32: Orthopedic Injuries\n'
                      'SKILLS: Hands On Skills; Toxicology; Psychiatric; Gynecology'),
    dict(date=date(2026, 10, 19), title='Week 12: CH 33-35',
         description='LECTURE: CH 33: Environmental Emergencies; CH 34: OB & Neonatal Care; '
                      'CH 35: Pediatric Emergencies\n'
                      'SKILLS: Hands On Skills; Trauma Overview; Soft Tissue'),
    dict(date=date(2026, 10, 26), title='Week 13: CH 36-38',
         description='NOTE: Week before Halloween — confirm facility availability\n'
                      'LECTURE: CH 36: Geriatric Emergencies; CH 37: Patients with Special Challenges; '
                      'CH 38: Transport Operations\n'
                      'SKILLS: Hands On Skills; Face & Neck Injuries; Head & Spine Injuries'),
    dict(date=date(2026, 11, 2), title='Week 14: CH 39-41',
         description='LECTURE: CH 39: Extrication / Hazardous Materials; CH 40: Incident Management; '
                      'CH 41: Terrorism Response\n'
                      'SKILLS: Hands On Skills; Chest Injuries; Abdominal / Orthopedic'),
    dict(date=date(2026, 11, 9), title='Week 15: Final Written Exam + Skills Lab',
         description='LECTURE: FINAL WRITTEN EXAM\n'
                      'SKILLS: Hands On Skills; Environmental Emergencies'),
]

DEADLINES = [
    dict(date=date(2026, 8, 16), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 1-3 due online'),
    dict(date=date(2026, 8, 23), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 4-6 due online'),
    dict(date=date(2026, 8, 30), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 7-9 due online'),
    dict(date=date(2026, 8, 30), event_type=CalendarEvent.EventType.EXAM,
         title='Section 1 Exam CH 1-9 due online'),
    dict(date=date(2026, 9, 6), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 10-11 due online'),
    dict(date=date(2026, 9, 6), event_type=CalendarEvent.EventType.EXAM,
         title='Section 2 Exam CH 10 due online'),
    dict(date=date(2026, 9, 13), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 12-13 (AEMT) / 14-16 (EMT) due online'),
    dict(date=date(2026, 9, 13), event_type=CalendarEvent.EventType.EXAM,
         title='Section 3 Exam CH 11 due online'),
    dict(date=date(2026, 9, 13), event_type=CalendarEvent.EventType.EXAM,
         title='Section 4 Exam CH 12 due online'),
    dict(date=date(2026, 9, 20), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 17-19 due online'),
    dict(date=date(2026, 9, 20), event_type=CalendarEvent.EventType.EXAM,
         title='Section 5 Exam CH 13-14 due online'),
    dict(date=date(2026, 9, 20), event_type=CalendarEvent.EventType.EXAM,
         title='Section 6A Exam CH 15-19 due online'),
    dict(date=date(2026, 9, 27), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 20-22 due online'),
    dict(date=date(2026, 10, 4), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 23-25 due online'),
    dict(date=date(2026, 10, 4), event_type=CalendarEvent.EventType.EXAM,
         title='Section 6B Exam CH 20-24 due online'),
    dict(date=date(2026, 10, 11), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 26-28 due online'),
    dict(date=date(2026, 10, 18), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 29-31 due online'),
    dict(date=date(2026, 10, 18), event_type=CalendarEvent.EventType.EXAM,
         title='Section 7A Exam CH 25-29 due online'),
    dict(date=date(2026, 10, 25), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 32-33 due online'),
    dict(date=date(2026, 10, 25), event_type=CalendarEvent.EventType.EXAM,
         title='Section 7B Exam CH 30-33 due online'),
    dict(date=date(2026, 11, 1), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 34-36 due online'),
    dict(date=date(2026, 11, 8), event_type=CalendarEvent.EventType.QUIZ,
         title='Quizzes 37-42 due online'),
    dict(date=date(2026, 11, 8), event_type=CalendarEvent.EventType.EXAM,
         title='Section 8 Exam CH 34-37 due online'),
    dict(date=date(2026, 11, 8), event_type=CalendarEvent.EventType.EXAM,
         title='Section 9 Exam CH 38-41 due online'),
]


class Command(BaseCommand):
    help = 'Seed the Fall 2026 EMT Hybrid / AEMT Hybrid Bridge class schedule and deadlines'

    def handle(self, *args, **kwargs):
        courses = list(Course.objects.filter(option_number__in=COURSE_OPTION_NUMBERS))
        if len(courses) != len(COURSE_OPTION_NUMBERS):
            found = {c.option_number for c in courses}
            missing = set(COURSE_OPTION_NUMBERS) - found
            self.stderr.write(self.style.ERROR(f'Missing course option_number(s): {sorted(missing)}'))
            return

        session_count = 0
        for course in courses:
            for s in SESSIONS:
                obj, created = CalendarEvent.objects.update_or_create(
                    course=course,
                    date=s['date'],
                    event_type=CalendarEvent.EventType.SESSION,
                    title=s['title'],
                    defaults=dict(
                        description=s['description'],
                        all_day=False,
                        start_time=time(18, 0),
                        end_time=time(21, 0),
                        location=LOCATION,
                    ),
                )
                session_count += 1

        deadline_count = 0
        for course in courses:
            for d in DEADLINES:
                obj, created = CalendarEvent.objects.update_or_create(
                    course=course,
                    date=d['date'],
                    event_type=d['event_type'],
                    title=d['title'],
                    defaults=dict(
                        description='',
                        all_day=True,
                        start_time=None,
                        end_time=None,
                        location='',
                    ),
                )
                deadline_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nSeeded {session_count} class-session events and {deadline_count} deadline events '
            f'across {len(courses)} course(s) (option {COURSE_OPTION_NUMBERS}).'
        ))
