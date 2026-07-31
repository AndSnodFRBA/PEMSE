from django.conf import settings
from django.db import models


class CalendarEvent(models.Model):
    """A single calendar entry for a course — due date, exam, quiz, topic, etc.

    Owned by whichever instructor/staff member created it; visible to every
    student enrolled in the linked course and included in that course's ICS
    feed so students can subscribe from their phone's calendar app.
    """

    class EventType(models.TextChoices):
        DUE_DATE = 'due_date', 'Assignment Due'
        EXAM     = 'exam',     'Exam'
        QUIZ     = 'quiz',     'Quiz'
        TOPIC    = 'topic',    'Class Topic'
        SESSION  = 'session',  'Class Session'
        OTHER    = 'other',    'Other'

    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='calendar_events',
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices, default=EventType.OTHER)
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    date       = models.DateField()
    all_day    = models.BooleanField(default=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time   = models.TimeField(null=True, blank=True)
    location   = models.CharField(max_length=200, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='calendar_events_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'start_time']

    def __str__(self):
        return f'[{self.course.tag}] {self.get_event_type_display()} — {self.title} ({self.date})'
