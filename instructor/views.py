from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from courses.models import Course, CourseEnrollment
from documents.models import InstructorDocument
from schedule.forms import CalendarEventForm
from schedule.models import CalendarEvent
from staff.models import StudentInvitation
from students.forms import StudentLoginForm
from students.models import (
    CognitiveExamRecord, PatientContactRecord,
    PsychomotorSkillRecord, Student,
)
from .forms import (
    AttendanceSessionForm,
    HourLogForm,
    InstructorDocumentForm,
    InstructorProfileForm,
    StudentAttendanceForm,
)
from .mixins import instructor_required
from .models import (
    AttendanceRecord,
    InstructionalHourLog,
    InstructorCourseAssignment,
    InstructorMeeting,
    InstructorNote,
    InstructorObservation,
    RemediationPlan,
    StudentAttendance,
)


# ── Auth ──────────────────────────────────────────────────────────────────────

def instructor_login_view(request):
    if request.user.is_authenticated:
        if request.user.is_instructor:
            return redirect('instructor_dashboard')
        if request.user.is_office_staff:
            return redirect('staff_dashboard')
        return redirect('dashboard')

    form = StudentLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        if not user.is_instructor:
            messages.error(request, 'This login is for instructors only.')
        else:
            login(request, user)
            return redirect('instructor_dashboard')

    return render(request, 'instructor/login.html', {'form': form})


def instructor_logout_view(request):
    logout(request)
    return redirect('instructor_login')


# ── Dashboard ─────────────────────────────────────────────────────────────────

@instructor_required
def instructor_dashboard(request):
    instructor = request.user
    today      = timezone.now().date()

    assignments = InstructorCourseAssignment.objects.filter(
        instructor=instructor, is_active=True
    ).select_related('course')

    course_ids = assignments.values_list('course_id', flat=True)

    # Hours summary
    first_of_month = today.replace(day=1)
    hours_this_month = InstructionalHourLog.objects.filter(
        instructor=instructor, session_date__gte=first_of_month
    ).aggregate(total=Sum('hours'))['total'] or Decimal('0')

    hours_total = InstructionalHourLog.objects.filter(
        instructor=instructor
    ).aggregate(total=Sum('hours'))['total'] or Decimal('0')

    # Verified hours this month, broken down by session type
    session_type_labels = dict(InstructionalHourLog.SESSION_TYPES)
    hours_by_type = InstructionalHourLog.objects.filter(
        instructor=instructor, session_date__gte=first_of_month, verified=True,
    ).values('session_type').annotate(total=Sum('hours')).order_by('-total')
    hours_by_type = [
        {'label': session_type_labels.get(row['session_type'], row['session_type']), 'hours': row['total']}
        for row in hours_by_type
    ]

    unverified_hours_this_month = InstructionalHourLog.objects.filter(
        instructor=instructor, session_date__gte=first_of_month, verified=False,
    ).aggregate(total=Sum('hours'))['total'] or Decimal('0')

    # Progress toward the "majority of class sessions" requirement, 172 NAC 13-004(B)(ii)(1):
    # what share of this month's logged sessions, across this instructor's assigned courses,
    # were taught by this instructor.
    course_ids = list(course_ids)
    sessions_this_month_all = InstructionalHourLog.objects.filter(
        course_id__in=course_ids, session_date__gte=first_of_month,
    ).count()
    sessions_this_month_mine = InstructionalHourLog.objects.filter(
        instructor=instructor, course_id__in=course_ids, session_date__gte=first_of_month,
    ).count()
    majority_pct = (
        round(sessions_this_month_mine / sessions_this_month_all * 100) if sessions_this_month_all else 0
    )

    # Recent attendance sessions
    recent_attendance = AttendanceRecord.objects.filter(
        instructor=instructor
    ).select_related('course').order_by('-session_date')[:5]

    # Pending observation acknowledgments
    pending_obs = InstructorObservation.objects.filter(
        instructor=instructor, instructor_acknowledged=False
    ).order_by('-observation_date')

    # Pending meeting acknowledgments
    pending_meetings = InstructorMeeting.objects.filter(
        instructor=instructor, instructor_acknowledged=False
    ).order_by('-meeting_date')

    # License expiry warning (within 90 days)
    license_warning = None
    if instructor.instructor_license_expiry:
        days_until = (instructor.instructor_license_expiry - today).days
        if days_until <= 90:
            license_warning = {'days': days_until, 'expiry': instructor.instructor_license_expiry}

    # Build course summary cards
    course_cards = []
    next_class = None
    for assignment in assignments:
        course = assignment.course
        enrolled_count = CourseEnrollment.objects.filter(course=course).count()
        next_session = AttendanceRecord.objects.filter(
            course=course, session_date__gte=today
        ).order_by('session_date').first()
        next_class_event = CalendarEvent.next_session(course)
        course_cards.append({
            'assignment':       assignment,
            'course':           course,
            'enrolled':         enrolled_count,
            'next_session':     next_session,
            'next_class_event': next_class_event,
        })
        if next_class_event and (next_class is None or next_class_event.date < next_class.date):
            next_class = next_class_event

    return render(request, 'instructor/dashboard.html', {
        'course_cards':      course_cards,
        'hours_this_month':  hours_this_month,
        'hours_total':       hours_total,
        'recent_attendance': recent_attendance,
        'pending_obs':       pending_obs,
        'pending_meetings':  pending_meetings,
        'license_warning':   license_warning,
        'next_class':        next_class,
        'hours_by_type':               hours_by_type,
        'unverified_hours_this_month': unverified_hours_this_month,
        'majority_pct':                majority_pct,
        'sessions_this_month_mine':    sessions_this_month_mine,
        'sessions_this_month_all':     sessions_this_month_all,
    })


# ── Hour Logging ──────────────────────────────────────────────────────────────

@instructor_required
def instructor_hours(request):
    instructor = request.user
    today      = timezone.now().date()
    first_of_month = today.replace(day=1)

    logs = InstructionalHourLog.objects.filter(
        instructor=instructor
    ).select_related('course', 'verified_by').order_by('-session_date')

    # Monthly summary by type
    monthly_summary = {}
    for stype, label in InstructionalHourLog.SESSION_TYPES:
        total = logs.filter(
            session_type=stype, session_date__gte=first_of_month
        ).aggregate(t=Sum('hours'))['t'] or Decimal('0')
        if total:
            monthly_summary[label] = total

    monthly_total = logs.filter(
        session_date__gte=first_of_month
    ).aggregate(t=Sum('hours'))['t'] or Decimal('0')

    overall_total = logs.aggregate(t=Sum('hours'))['t'] or Decimal('0')

    return render(request, 'instructor/hours.html', {
        'logs':            logs,
        'monthly_summary': monthly_summary,
        'monthly_total':   monthly_total,
        'overall_total':   overall_total,
        'this_month':      first_of_month,
    })


@instructor_required
def instructor_hours_add(request):
    instructor = request.user
    form = HourLogForm(instructor, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        log            = form.save(commit=False)
        log.instructor = instructor
        log.save()
        messages.success(request, f'Hour log entry added — {log.hours} hours on {log.session_date}.')
        return redirect('instructor_hours')
    return render(request, 'instructor/hours_add.html', {'form': form})


@instructor_required
def instructor_hours_edit(request, pk):
    instructor = request.user
    log = get_object_or_404(InstructionalHourLog, pk=pk, instructor=instructor)
    if log.verified:
        messages.error(request, 'Verified hours cannot be edited.')
        return redirect('instructor_hours')
    form = HourLogForm(instructor, request.POST or None, instance=log)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Hour log updated.')
        return redirect('instructor_hours')
    return render(request, 'instructor/hours_edit.html', {'form': form, 'log': log})


@instructor_required
def instructor_hours_delete(request, pk):
    instructor = request.user
    log = get_object_or_404(InstructionalHourLog, pk=pk, instructor=instructor)
    if log.verified:
        messages.error(request, 'Verified hours cannot be deleted.')
    elif request.method == 'POST':
        log.delete()
        messages.success(request, 'Hour log entry deleted.')
    return redirect('instructor_hours')


@instructor_required
def instructor_hours_pdf(request):
    """Generate a PDF report of hour logs for a date range."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    import io

    instructor = request.user
    start_str = request.GET.get('start')
    end_str   = request.GET.get('end')

    logs = InstructionalHourLog.objects.filter(instructor=instructor).order_by('session_date')
    if start_str:
        from datetime import datetime
        try:
            logs = logs.filter(session_date__gte=datetime.strptime(start_str, '%Y-%m-%d').date())
        except ValueError:
            pass
    if end_str:
        from datetime import datetime
        try:
            logs = logs.filter(session_date__lte=datetime.strptime(end_str, '%Y-%m-%d').date())
        except ValueError:
            pass

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    navy = colors.HexColor('#1a2e4a')
    elems = []

    elems.append(Paragraph('Panhandle EMS Education', styles['Title']))
    elems.append(Paragraph(f'Instructor Hour Log — {instructor.get_full_name()}', styles['Heading2']))
    elems.append(Spacer(1, 12))

    data = [['Date', 'Course', 'Type', 'Topic', 'Hrs', 'Students', 'Verified']]
    for log in logs:
        data.append([
            str(log.session_date),
            log.course.tag,
            log.get_session_type_display(),
            log.topic_covered[:40],
            str(log.hours),
            str(log.students_present),
            '✓' if log.verified else '—',
        ])
    total = logs.aggregate(t=Sum('hours'))['t'] or 0
    data.append(['', '', '', 'TOTAL', str(total), '', ''])

    t = Table(data, colWidths=[65, 50, 80, 150, 35, 55, 45])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTSIZE',   (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f0f4f8')]),
        ('FONTNAME',   (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#dde4ef')),
    ]))
    elems.append(t)

    doc.build(elems)
    buf.seek(0)
    name = instructor.get_full_name().replace(' ', '_')
    response = HttpResponse(buf, content_type='application/pdf')
    response['Content-Disposition'] = f'filename="hour_log_{name}.pdf"'
    return response


# ── Attendance ────────────────────────────────────────────────────────────────

@instructor_required
def instructor_attendance(request):
    instructor = request.user
    sessions = AttendanceRecord.objects.filter(
        instructor=instructor
    ).select_related('course').annotate(
        student_count=Count('student_attendance')
    ).order_by('-session_date')
    return render(request, 'instructor/attendance.html', {'sessions': sessions})


@instructor_required
def instructor_attendance_add(request):
    instructor = request.user
    form = AttendanceSessionForm(instructor, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        session            = form.save(commit=False)
        session.instructor = instructor
        session.save()
        # Pre-populate StudentAttendance for all enrolled students (default=Present)
        enrolled_students = CourseEnrollment.objects.filter(
            course=session.course
        ).select_related('student')
        for enrollment in enrolled_students:
            StudentAttendance.objects.get_or_create(
                session=session,
                student=enrollment.student,
                defaults={'status': StudentAttendance.Status.PRESENT},
            )
        messages.success(request, f'Attendance session created for {session.session_date}. Take roll below.')
        return redirect('instructor_attendance_detail', pk=session.pk)
    return render(request, 'instructor/attendance_add.html', {'form': form})


@instructor_required
def instructor_attendance_detail(request, pk):
    instructor = request.user
    session = get_object_or_404(AttendanceRecord, pk=pk, instructor=instructor)
    attendances = session.student_attendance.select_related('student').order_by(
        'student__last_name', 'student__first_name'
    )
    counts = {
        'present': attendances.filter(status='present').count(),
        'absent':  attendances.filter(status='absent').count(),
        'late':    attendances.filter(status='late').count(),
        'excused': attendances.filter(status='excused').count(),
    }
    return render(request, 'instructor/attendance_detail.html', {
        'session':     session,
        'attendances': attendances,
        'counts':      counts,
        'can_edit':    session.is_editable,
    })


@instructor_required
def instructor_attendance_edit(request, pk):
    instructor = request.user
    session = get_object_or_404(AttendanceRecord, pk=pk, instructor=instructor)
    if not session.is_editable:
        messages.error(request, 'Attendance records are locked 48 hours after the session.')
        return redirect('instructor_attendance_detail', pk=pk)

    attendances = list(session.student_attendance.select_related('student').order_by(
        'student__last_name', 'student__first_name'
    ))

    if request.method == 'POST':
        all_valid = True
        for att in attendances:
            prefix = f'att_{att.pk}'
            status       = request.POST.get(f'{prefix}_status', att.status)
            arrival_time = request.POST.get(f'{prefix}_arrival_time') or None
            note         = request.POST.get(f'{prefix}_notes', '')
            att.status       = status
            att.notes        = note
            if arrival_time:
                from datetime import datetime
                try:
                    att.arrival_time = datetime.strptime(arrival_time, '%H:%M').time()
                except ValueError:
                    att.arrival_time = None
            else:
                att.arrival_time = None
            att.save()
        messages.success(request, 'Attendance updated.')
        return redirect('instructor_attendance_detail', pk=pk)

    return render(request, 'instructor/attendance_edit.html', {
        'session':     session,
        'attendances': attendances,
    })


# ── Courses ───────────────────────────────────────────────────────────────────

@instructor_required
def instructor_courses(request):
    instructor  = request.user
    assignments = InstructorCourseAssignment.objects.filter(
        instructor=instructor, is_active=True
    ).select_related('course').order_by('course__start_date')
    return render(request, 'instructor/courses.html', {'assignments': assignments})


@instructor_required
def instructor_course_detail(request, pk):
    instructor  = request.user
    course      = get_object_or_404(Course, pk=pk)
    assignment  = get_object_or_404(
        InstructorCourseAssignment, instructor=instructor, course=course, is_active=True
    )
    enrollments = CourseEnrollment.objects.filter(course=course).select_related('student')

    # Attendance summary per student
    all_sessions = AttendanceRecord.objects.filter(course=course)
    total_sessions = all_sessions.count()

    student_rows = []
    for enrollment in enrollments:
        student = enrollment.student
        att_records = StudentAttendance.objects.filter(
            session__course=course, student=student
        )
        present_count = att_records.filter(status='present').count()
        absent_count  = att_records.filter(status='absent').count()
        late_count    = att_records.filter(status='late').count()
        pct = round(present_count / total_sessions * 100) if total_sessions else None
        student_rows.append({
            'student':       student,
            'present':       present_count,
            'absent':        absent_count,
            'late':          late_count,
            'total_sessions': total_sessions,
            'pct':           pct,
            'low_attendance': pct is not None and pct < 80,
        })

    hour_logs = InstructionalHourLog.objects.filter(
        instructor=instructor, course=course
    ).order_by('-session_date')
    hours_total = hour_logs.aggregate(t=Sum('hours'))['t'] or Decimal('0')

    sessions = AttendanceRecord.objects.filter(
        course=course, instructor=instructor
    ).order_by('-session_date')[:10]

    invitations = StudentInvitation.objects.filter(
        course=course
    ).select_related('created_by').order_by('-created_at')

    return render(request, 'instructor/course_detail.html', {
        'course':        course,
        'assignment':    assignment,
        'student_rows':  student_rows,
        'hour_logs':     hour_logs,
        'hours_total':   hours_total,
        'sessions':      sessions,
        'total_sessions': total_sessions,
        'invitations':   invitations,
    })


# ── Documents ─────────────────────────────────────────────────────────────────

@instructor_required
def instructor_documents(request):
    docs = InstructorDocument.objects.filter(uploaded_by=request.user).select_related('course')
    return render(request, 'instructor/documents.html', {'docs': docs})


@instructor_required
def instructor_document_add(request):
    form = InstructorDocumentForm(request.user, request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        doc = form.save(commit=False)
        doc.uploaded_by = request.user
        doc.save()
        messages.success(request, f'"{doc.title}" uploaded — visible to students now.')
        return redirect('instructor_documents')
    return render(request, 'instructor/document_add.html', {'form': form})


@instructor_required
def instructor_document_edit(request, pk):
    doc  = get_object_or_404(InstructorDocument, pk=pk, uploaded_by=request.user)
    form = InstructorDocumentForm(request.user, request.POST or None, request.FILES or None, instance=doc)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'"{doc.title}" updated.')
        return redirect('instructor_documents')
    return render(request, 'instructor/document_add.html', {'form': form, 'doc': doc})


@instructor_required
def instructor_document_delete(request, pk):
    doc = get_object_or_404(InstructorDocument, pk=pk, uploaded_by=request.user)
    if request.method == 'POST':
        doc.file.delete(save=False)
        doc.delete()
        messages.success(request, 'Document removed.')
    return redirect('instructor_documents')


# ── Student Detail (read-only for instructor) ─────────────────────────────────

@instructor_required
def instructor_student_detail(request, pk):
    instructor = request.user
    student    = get_object_or_404(Student, pk=pk, role=Student.Role.STUDENT)

    # Verify student is in one of instructor's courses
    instructor_course_ids = InstructorCourseAssignment.objects.filter(
        instructor=instructor, is_active=True
    ).values_list('course_id', flat=True)
    enrollment = CourseEnrollment.objects.filter(
        student=student, course_id__in=instructor_course_ids
    ).select_related('course').first()
    if not enrollment:
        messages.error(request, 'This student is not in one of your courses.')
        return redirect('instructor_courses')

    course = enrollment.course

    # Attendance for this course
    all_sessions = AttendanceRecord.objects.filter(course=course)
    total_sessions = all_sessions.count()
    att_records = StudentAttendance.objects.filter(session__course=course, student=student)
    present_count = att_records.filter(status='present').count()
    absent_count  = att_records.filter(status='absent').count()
    late_count    = att_records.filter(status='late').count()
    att_pct = round(present_count / total_sessions * 100) if total_sessions else None

    cognitive_exams    = CognitiveExamRecord.objects.filter(student=student, course=course)
    psychomotor_skills = PsychomotorSkillRecord.objects.filter(student=student, course=course)
    patient_contacts   = PatientContactRecord.objects.filter(student=student, course=course)

    pc_totals = {
        'total':           patient_contacts.count(),
        'iv_attempted':    patient_contacts.filter(iv_start_attempted=True).count(),
        'iv_successful':   patient_contacts.filter(iv_start_successful=True).count(),
        'airway_attempted': patient_contacts.filter(airway_placement_attempted=True).count(),
        'airway_successful': patient_contacts.filter(airway_placement_successful=True).count(),
    }
    is_aemt = course.licensure in ('AEMT', 'PARA')

    # Instructor notes for this student
    notes = InstructorNote.objects.filter(
        instructor=instructor, student=student
    ).order_by('-created_at')

    if request.method == 'POST' and 'note_text' in request.POST:
        note_text = request.POST['note_text'].strip()
        if note_text:
            InstructorNote.objects.create(
                instructor=instructor,
                student=student,
                course=course,
                note=note_text,
            )
            messages.success(request, 'Note added.')
            return redirect('instructor_student_detail', pk=pk)

    return render(request, 'instructor/student_detail.html', {
        'student':           student,
        'enrollment':        enrollment,
        'course':            course,
        'total_sessions':    total_sessions,
        'present_count':     present_count,
        'absent_count':      absent_count,
        'late_count':        late_count,
        'att_pct':           att_pct,
        'att_records':       att_records.select_related('session').order_by('-session__session_date'),
        'cognitive_exams':   cognitive_exams,
        'psychomotor_skills': psychomotor_skills,
        'patient_contacts':  patient_contacts,
        'pc_totals':         pc_totals,
        'is_aemt':           is_aemt,
        'notes':             notes,
    })


# ── Profile ───────────────────────────────────────────────────────────────────

@instructor_required
def instructor_profile(request):
    instructor = request.user
    form = InstructorProfileForm(request.POST or None, instance=instructor)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated.')
        return redirect('instructor_profile')
    return render(request, 'instructor/profile.html', {'form': form})


# ── Observations (read-only) ───────────────────────────────────────────────────

@instructor_required
def instructor_observations(request):
    instructor   = request.user
    observations = InstructorObservation.objects.filter(
        instructor=instructor
    ).select_related('course', 'observed_by').order_by('-observation_date')
    return render(request, 'instructor/observations.html', {'observations': observations})


@instructor_required
def instructor_observation_acknowledge(request, pk):
    instructor  = request.user
    observation = get_object_or_404(InstructorObservation, pk=pk, instructor=instructor)
    if request.method == 'POST':
        observation.instructor_acknowledged    = True
        observation.instructor_acknowledged_at = timezone.now()
        observation.instructor_response        = request.POST.get('response', '')
        observation.save()
        messages.success(request, 'Observation acknowledged.')
    return redirect('instructor_observations')


# ── Meetings ──────────────────────────────────────────────────────────────────

@instructor_required
def instructor_meetings(request):
    instructor = request.user
    meetings   = InstructorMeeting.objects.filter(
        instructor=instructor
    ).select_related('conducted_by').order_by('-meeting_date')
    return render(request, 'instructor/meetings.html', {'meetings': meetings})


@instructor_required
def instructor_meeting_acknowledge(request, pk):
    instructor = request.user
    meeting    = get_object_or_404(InstructorMeeting, pk=pk, instructor=instructor)
    if request.method == 'POST':
        sig = request.POST.get('signature', '')
        meeting.instructor_acknowledged    = True
        meeting.instructor_acknowledged_at = timezone.now()
        meeting.instructor_signature       = sig
        meeting.save()
        messages.success(request, 'Meeting record acknowledged and signed.')
    return redirect('instructor_meetings')


# ── Calendar ──────────────────────────────────────────────────────────────────

def _instructor_courses_qs(instructor):
    course_ids = InstructorCourseAssignment.objects.filter(
        instructor=instructor, is_active=True
    ).values_list('course_id', flat=True)
    return Course.objects.filter(pk__in=course_ids)


@instructor_required
def instructor_calendar(request):
    instructor = request.user
    events = CalendarEvent.objects.filter(
        course__in=_instructor_courses_qs(instructor)
    ).select_related('course').order_by('date', 'start_time')

    today = timezone.now().date()
    return render(request, 'instructor/calendar.html', {
        'upcoming_events': [e for e in events if e.date >= today],
        'past_events':     [e for e in events if e.date < today],
        'feed_token':      instructor.calendar_token,
    })


@instructor_required
def instructor_calendar_add(request):
    instructor = request.user
    form = CalendarEventForm(_instructor_courses_qs(instructor), request.POST or None)
    if request.method == 'POST' and form.is_valid():
        event            = form.save(commit=False)
        event.created_by = instructor
        event.save()
        messages.success(request, f'Added "{event.title}" to the calendar.')
        return redirect('instructor_calendar')
    return render(request, 'instructor/calendar_form.html', {'form': form})


@instructor_required
def instructor_calendar_edit(request, pk):
    instructor = request.user
    event = get_object_or_404(CalendarEvent, pk=pk, course__in=_instructor_courses_qs(instructor))
    form = CalendarEventForm(_instructor_courses_qs(instructor), request.POST or None, instance=event)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Calendar event updated.')
        return redirect('instructor_calendar')
    return render(request, 'instructor/calendar_form.html', {'form': form, 'event': event})


@instructor_required
def instructor_calendar_delete(request, pk):
    instructor = request.user
    event = get_object_or_404(CalendarEvent, pk=pk, course__in=_instructor_courses_qs(instructor))
    if request.method == 'POST':
        event.delete()
        messages.success(request, 'Calendar event deleted.')
    return redirect('instructor_calendar')
