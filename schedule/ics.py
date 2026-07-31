"""Minimal RFC 5545 (iCalendar) writer — no third-party dependency required.

Builds a VCALENDAR feed of CalendarEvent rows so students/instructors can
subscribe from a phone calendar app (webcal://) and have it stay in sync.
"""
from datetime import datetime, timedelta

from django.utils import timezone

CRLF = '\r\n'


def _escape(text):
    text = text or ''
    return (
        text.replace('\\', '\\\\')
            .replace(';', '\\;')
            .replace(',', '\\,')
            .replace('\n', '\\n')
    )


def _fold(line):
    """Fold lines longer than 75 octets per RFC 5545 §3.1."""
    if len(line.encode('utf-8')) <= 75:
        return line
    out = []
    while len(line.encode('utf-8')) > 75:
        # naive char-based split is fine for our ASCII-heavy content
        out.append(line[:75])
        line = ' ' + line[75:]
    out.append(line)
    return CRLF.join(out)


def _event_to_vevent(event, dtstamp):
    uid = f'pemse-event-{event.pk}@panhandleems.education'
    lines = ['BEGIN:VEVENT', f'UID:{uid}', f'DTSTAMP:{dtstamp}']

    if event.all_day or not event.start_time:
        dtstart = event.date.strftime('%Y%m%d')
        dtend   = (event.date + timedelta(days=1)).strftime('%Y%m%d')
        lines.append(f'DTSTART;VALUE=DATE:{dtstart}')
        lines.append(f'DTEND;VALUE=DATE:{dtend}')
    else:
        start = datetime.combine(event.date, event.start_time)
        end   = datetime.combine(event.date, event.end_time or event.start_time)
        lines.append(f'DTSTART:{start.strftime("%Y%m%dT%H%M%S")}')
        lines.append(f'DTEND:{end.strftime("%Y%m%dT%H%M%S")}')

    summary = f'[{event.course.tag}] {event.get_event_type_display()}: {event.title}'
    lines.append(_fold(f'SUMMARY:{_escape(summary)}'))
    if event.description:
        lines.append(_fold(f'DESCRIPTION:{_escape(event.description)}'))
    if event.location:
        lines.append(_fold(f'LOCATION:{_escape(event.location)}'))
    lines.append(f'CATEGORIES:{_escape(event.get_event_type_display())}')
    lines.append('END:VEVENT')
    return lines


def build_calendar(events, calendar_name):
    dtstamp = timezone.now().strftime('%Y%m%dT%H%M%SZ')
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//PEMSE//Course Calendar//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        _fold(f'X-WR-CALNAME:{_escape(calendar_name)}'),
        'REFRESH-INTERVAL;VALUE=DURATION:PT12H',
        'X-PUBLISHED-TTL:PT12H',
    ]
    for event in events:
        lines.extend(_event_to_vevent(event, dtstamp))
    lines.append('END:VCALENDAR')
    return CRLF.join(lines) + CRLF
