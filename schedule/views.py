import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import slugify

from students.models import Student
from .calendar_copy import apply_copy, plan_copy
from .forms import CalendarCopyForm
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


def copy_calendar_page(request, *, source_courses, target_courses, portal):
    """Shared staff/instructor "Copy From Course" page: preview, then copy.

    `portal` is 'staff' or 'instructor' — picks the base template and the
    calendar page to return to.
    """
    form = CalendarCopyForm(
        source_courses, target_courses, request.POST or None,
        initial={'target': request.GET.get('target')},
    )
    plan = None
    calendar_url = reverse(f'{portal}_calendar')

    if request.method == 'POST' and form.is_valid():
        source = form.cleaned_data['source']
        target = form.cleaned_data['target']
        plan = plan_copy(source, target, form.cleaned_data['new_start'])

        if plan is None:
            form.add_error('source', 'That course has no calendar events to copy.')
        elif request.POST.get('action') == 'confirm':
            created = apply_copy(plan, target, request.user)
            skipped = len(plan.events) - created
            msg = f'Copied {created} event{"s" if created != 1 else ""} from {source.tag} to {target.name}.'
            if skipped:
                msg += f' Skipped {skipped} already on that calendar.'
            messages.success(request, msg)
            if portal == 'staff':
                calendar_url += f'?course={target.pk}'
            return redirect(calendar_url)

    return render(request, 'schedule/calendar_copy.html', {
        'form': form,
        'plan': plan,
        'base_template': f'{portal}/base_{portal}.html',
        'css_prefix': 'staff' if portal == 'staff' else 'inst',
        'calendar_url': calendar_url,
    })
