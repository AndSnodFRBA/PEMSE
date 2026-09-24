"""Copy one course's calendar onto another course, shifted to a new start date.

Lets a finished class serve as the template for the next cohort: every event
is re-dated by the same whole-week offset, so Monday sessions stay on Mondays
and Sunday deadlines stay on Sundays.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction

from .models import CalendarEvent


@dataclass
class PlannedEvent:
    source: CalendarEvent
    new_date: date
    already_exists: bool


@dataclass
class CopyPlan:
    anchor: date            # source course's first class session (or first event)
    new_start: date         # anchor shifted — always the same weekday as anchor
    requested_start: date   # what the user typed; differs from new_start if snapped
    events: list

    @property
    def was_snapped(self):
        return self.new_start != self.requested_start

    @property
    def to_create(self):
        return [p for p in self.events if not p.already_exists]


def anchor_date(source_course):
    """First class session of the source course, falling back to its first event."""
    events = CalendarEvent.objects.filter(course=source_course).order_by('date')
    first_session = events.filter(event_type=CalendarEvent.EventType.SESSION).first()
    first_event = first_session or events.first()
    return first_event.date if first_event else None


def plan_copy(source_course, target_course, requested_start):
    """Work out the new date for every source event without saving anything.

    Returns None if the source course has no events.
    """
    anchor = anchor_date(source_course)
    if anchor is None:
        return None

    # Whole weeks only, so every event keeps its weekday.
    weeks = round((requested_start - anchor).days / 7)
    offset = timedelta(weeks=weeks)

    existing = set(
        CalendarEvent.objects.filter(course=target_course)
        .values_list('date', 'event_type', 'title')
    )

    planned = []
    for event in CalendarEvent.objects.filter(course=source_course).order_by('date', 'start_time'):
        new_date = event.date + offset
        planned.append(PlannedEvent(
            source=event,
            new_date=new_date,
            already_exists=(new_date, event.event_type, event.title) in existing,
        ))

    return CopyPlan(anchor=anchor, new_start=anchor + offset,
                    requested_start=requested_start, events=planned)


@transaction.atomic
def apply_copy(plan, target_course, user):
    """Create the planned events on the target course. Skips any that already
    exist there (same date, type, and title), so re-running is harmless."""
    created = []
    for p in plan.to_create:
        e = p.source
        created.append(CalendarEvent(
            course=target_course,
            event_type=e.event_type,
            title=e.title,
            description=e.description,
            date=p.new_date,
            all_day=e.all_day,
            start_time=e.start_time,
            end_time=e.end_time,
            location=e.location,
            created_by=user,
        ))
    CalendarEvent.objects.bulk_create(created)
    return len(created)
