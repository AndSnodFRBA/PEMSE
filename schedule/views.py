import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import redirect

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

    course_ids = user.calendar_courses.values_list('pk', flat=True)
    events = CalendarEvent.objects.filter(course_id__in=course_ids).select_related('course')
    ics_text = build_calendar(events, calendar_name=f'PEMSE — {user.get_full_name()}')

    response = HttpResponse(ics_text, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'inline; filename="pemse-calendar.ics"'
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
