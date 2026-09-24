import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import redirect
from django.utils.text import slugify

from students.models import Student
from .ics import build_calendar
from .models import CalendarEvent


def calendar_feed(request, token):
    """Public, token-authenticated ICS feed — no login required so phone
    calendar apps can poll it on their own schedule."""
    try:
        user = Student.objects.get(calendar_token=token)
    except (Student.DoesNotExist, ValueError):
        raise Http404('Unknown calendar feed.')

    courses = user.calendar_courses
    course_ids = courses.values_list('pk', flat=True)
    events = CalendarEvent.objects.filter(course_id__in=course_ids).select_related('course')

    course_names = list(courses.values_list('name', flat=True))
    if not course_names:
        label = 'No Course'
    elif len(course_names) <= 3:
        label = ', '.join(course_names)
    else:
        label = f'{len(course_names)} Courses'
    ics_text = build_calendar(events, calendar_name=f'{settings.AGENCY_SHORT_NAME} — {label}')

    return _ics_response(ics_text, 'pemse-calendar.ics')


def calendar_course_feed(request, token, course_id):
    """Single-course ICS feed, so each class shows up as its own calendar
    on the subscriber's phone. Same token auth as the combined feed; the
    course must be one the token's owner can see."""
    try:
        user = Student.objects.get(calendar_token=token)
    except (Student.DoesNotExist, ValueError):
        raise Http404('Unknown calendar feed.')

    course = user.calendar_courses.filter(pk=course_id).first()
    if course is None:
        raise Http404('Unknown calendar feed.')

    events = CalendarEvent.objects.filter(course=course).select_related('course')
    ics_text = build_calendar(
        events, calendar_name=f'{settings.AGENCY_SHORT_NAME} — {course.tag}: {course.name}',
    )
    return _ics_response(ics_text, f'{slugify(course.tag)}-{course.pk}.ics')


def _ics_response(ics_text, filename):
    response = HttpResponse(ics_text, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
def regenerate_feed_token(request):
    """Invalidate the current subscribe link (e.g. if it was shared/leaked)."""
    if request.method == 'POST':
        request.user.calendar_token = uuid.uuid4()
        request.user.save(update_fields=['calendar_token'])
        messages.success(request, 'Your calendar subscription link has been reset. Update it on your phone.')

    if request.user.is_instructor:
        return redirect('instructor_calendar')
    if request.user.is_office_staff:
        return redirect('staff_calendar')
    return redirect('calendar')
