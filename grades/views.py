from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone

from staff.mixins import staff_required
from instructor.mixins import instructor_required
from django.contrib.auth.decorators import login_required

from students.models import Student
from courses.models import Course, CourseEnrollment
from instructor.models import InstructorCourseAssignment

from .models import (
    GradeBook, QuizGrade, SectionExamGrade, WorksheetGrade, SkillsGrade, ParticipationDeduction,
)
from .forms import (
    QuizGradeForm, SectionExamGradeForm, WorksheetGradeForm, SkillsGradeForm,
    ParticipationDeductionForm,
)
from .audit import log_grade_change


def _student_current_course(student):
    enrollment = CourseEnrollment.objects.filter(student=student).select_related('course').first()
    return enrollment.course if enrollment else None


def _get_or_none_gradebook(student):
    course = _student_current_course(student)
    if not course:
        return None, None
    gb = GradeBook.objects.filter(student=student, course=course).first()
    return gb, course


def certificate_requirements_checklist(student, enrollment, gradebook, completion_record):
    """The 6 conditions gating certificate generation — broader than
    GradeBook.meets_completion_requirements, which only covers the 3
    grade-based conditions (overall/section-exams/final). Certificate
    issuance also needs hours verified, paperwork complete, and the
    balance paid off."""
    from students.balance import compute_balance

    is_clinical_course = enrollment.course.licensure in ('AEMT', 'PARA')
    section_exams = gradebook.section_exam_grades.filter(is_final_exam=False)
    section_exams_passing = section_exams.filter(score__gte=75).count()
    section_exams_total = section_exams.count()

    hours_complete = (not is_clinical_course) or (completion_record.verification_date is not None)
    paperwork_complete = student.enrollment_complete
    _, _, _, balance_due = compute_balance(student)
    financial_complete = balance_due <= 0

    items = [
        {
            'label': 'Overall grade 75%+',
            'met': gradebook.is_passing,
            'detail': f'Current: {gradebook.overall_grade}%' if gradebook.overall_grade is not None else 'Not yet calculable',
        },
        {
            'label': 'All section exams 75%+',
            'met': bool(gradebook.section_exams_all_passing),
            'detail': f'{section_exams_passing} of {section_exams_total} passing',
        },
        {
            'label': 'Final exam 75%+',
            'met': gradebook.final_exam_score is not None and gradebook.final_exam_score >= 75,
            'detail': f'Score: {gradebook.final_exam_score}%' if gradebook.final_exam_score is not None else 'Not yet taken',
        },
        {
            'label': 'Field/clinical hours complete (for EMT/AEMT)',
            'met': hours_complete,
            'detail': 'N/A for this course' if not is_clinical_course else (
                'Verified by staff' if hours_complete else 'Not yet verified'
            ),
        },
        {
            'label': 'All required paperwork submitted',
            'met': paperwork_complete,
            'detail': 'Complete' if paperwork_complete else 'Incomplete',
        },
        {
            'label': 'Financial obligations fulfilled',
            'met': financial_complete,
            'detail': 'Paid in full' if financial_complete else f'Balance due: ${balance_due:,.2f}',
        },
    ]
    all_met = all(item['met'] for item in items)
    return items, all_met


def _notify_staff_if_at_risk(gradebook):
    """Notify staff when a grade drops a student below passing.
    Skips a staff member who already has an unread notification for this
    student — otherwise every subsequent grade edit while they remain below
    75% would re-spam the whole staff list."""
    if gradebook.overall_grade is None or gradebook.overall_grade >= 75:
        return
    from students.models import Student, StudentNotification
    title = f'{gradebook.student.get_full_name()} grade dropped below passing'
    for staff_user in Student.objects.filter(role__in=[Student.Role.STAFF, Student.Role.ADMIN]):
        already_notified = StudentNotification.objects.filter(
            student=staff_user, notif_type='general', title=title, is_read=False,
        ).exists()
        if not already_notified:
            StudentNotification.create(
                student=staff_user,
                notif_type='general',
                title=title,
                body=f'Current overall grade: {gradebook.overall_grade}%',
                link=f'/staff/grades/{gradebook.student_id}/',
            )


# ── Staff views ─────────────────────────────────────────────────────────────

@staff_required
def staff_grade_overview(request):
    course_filter = request.GET.get('course') or ''
    courses = Course.objects.filter(is_active=True).order_by('option_number')

    selected_course = None
    if course_filter:
        selected_course = Course.objects.filter(pk=course_filter).first()
    elif courses.exists():
        selected_course = courses.first()

    rows = []
    if selected_course:
        enrollments = CourseEnrollment.objects.filter(course=selected_course).select_related('student').order_by(
            'student__last_name', 'student__first_name'
        )
        for enrollment in enrollments:
            student = enrollment.student
            gb = GradeBook.objects.filter(student=student, course=selected_course).first()
            rows.append({'student': student, 'gradebook': gb})

    return render(request, 'grades/staff_overview.html', {
        'all_courses': courses,
        'selected_course': selected_course,
        'rows': rows,
    })


@staff_required
def staff_gradebook_detail(request, student_id):
    student = get_object_or_404(Student, pk=student_id, role=Student.Role.STUDENT)
    gb, course = _get_or_none_gradebook(student)
    course_ended = bool(course and course.end_date and course.end_date < timezone.now().date())

    checklist, certificate_available = None, False
    enrollment = None
    if gb and course:
        from students.models import CourseCompletionRecord
        enrollment = CourseEnrollment.objects.filter(student=student, course=course).first()
        completion_record = CourseCompletionRecord.objects.filter(student=student, course=course).first()
        if enrollment and completion_record:
            checklist, certificate_available = certificate_requirements_checklist(
                student, enrollment, gb, completion_record
            )

    return render(request, 'grades/staff_gradebook_detail.html', {
        'student': student,
        'course': course,
        'gb': gb,
        'course_ended': course_ended,
        'checklist': checklist,
        'certificate_available': certificate_available,
    })


@staff_required
def staff_gradebook_create(request, student_id):
    student = get_object_or_404(Student, pk=student_id, role=Student.Role.STUDENT)
    if request.method == 'POST':
        course = _student_current_course(student)
        if not course:
            messages.error(request, f'{student.get_full_name()} is not enrolled in a course yet.')
        else:
            GradeBook.objects.get_or_create(student=student, course=course)
            messages.success(request, 'Gradebook created.')
    return redirect('staff_gradebook_detail', student_id=student.pk)


@staff_required
def staff_quiz_edit(request, student_id, quiz_number):
    student = get_object_or_404(Student, pk=student_id, role=Student.Role.STUDENT)
    gb, course = _get_or_none_gradebook(student)
    if not gb:
        messages.error(request, 'Create a gradebook for this student first.')
        return redirect('staff_gradebook_detail', student_id=student.pk)

    quiz_number = int(quiz_number)
    instance = QuizGrade.objects.filter(gradebook=gb, quiz_number=quiz_number).first()

    if request.method == 'POST':
        if gb.is_finalized:
            return HttpResponseForbidden('Gradebook is finalized')
        was_create = instance is None
        old_score = instance.score if instance else ''
        was_reset_before = instance.was_reset if instance else False
        is_new_reset = bool(request.POST.get('was_reset')) and not was_reset_before
        if is_new_reset and gb.quiz_resets_remaining <= 0:
            messages.error(request, 'This student has used all 5 quiz resets allowed per the handbook')
            form = QuizGradeForm(request.POST, instance=instance)
            return render(request, 'grades/staff_quiz_form.html', {
                'student': student, 'gb': gb, 'form': form, 'quiz_number': quiz_number, 'instance': instance,
            })
        form = QuizGradeForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.gradebook = gb
            obj.quiz_number = quiz_number
            obj.entered_by = request.user
            obj.score = form.cleaned_data['score']
            obj.save()
            log_grade_change(
                gb, request.user, 'create' if was_create else 'update', 'QuizGrade', obj.pk,
                field_name='score', old_value=old_score, new_value=obj.score,
            )
            if is_new_reset and gb.quiz_resets_remaining == 1:
                messages.warning(request, 'This student has 1 quiz reset remaining')
            _notify_staff_if_at_risk(gb)
            messages.success(request, f'Quiz {quiz_number} grade saved.')
            return redirect('staff_gradebook_detail', student_id=student.pk)
    else:
        initial = {'quiz_name': f'Quiz {quiz_number}'} if not instance else None
        form = QuizGradeForm(instance=instance, initial=initial)

    return render(request, 'grades/staff_quiz_form.html', {
        'student': student, 'gb': gb, 'form': form, 'quiz_number': quiz_number, 'instance': instance,
    })


@staff_required
def staff_exam_edit(request, student_id, exam_id):
    student = get_object_or_404(Student, pk=student_id, role=Student.Role.STUDENT)
    gb, course = _get_or_none_gradebook(student)
    if not gb:
        messages.error(request, 'Create a gradebook for this student first.')
        return redirect('staff_gradebook_detail', student_id=student.pk)

    instance = None
    if exam_id != 'new':
        instance = get_object_or_404(SectionExamGrade, pk=exam_id, gradebook=gb)

    if request.method == 'POST':
        if gb.is_finalized:
            return HttpResponseForbidden('Gradebook is finalized')
        was_create = instance is None
        old_score = instance.score if instance else ''
        was_reset_before = instance.was_reset if instance else False
        is_final = bool(request.POST.get('is_final_exam'))
        is_new_reset = bool(request.POST.get('was_reset')) and not was_reset_before and not is_final
        if is_new_reset and gb.exam_resets_remaining <= 0:
            messages.error(request, 'This student has used both section exam resets allowed per the handbook')
            form = SectionExamGradeForm(request.POST, instance=instance)
            reset_warning = instance and instance.reset_count >= 2
            return render(request, 'grades/staff_exam_form.html', {
                'student': student, 'gb': gb, 'form': form, 'instance': instance, 'reset_warning': reset_warning,
            })
        form = SectionExamGradeForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.gradebook = gb
            obj.entered_by = request.user
            obj.score = form.cleaned_data['score']
            obj.save()
            log_grade_change(
                gb, request.user, 'create' if was_create else 'update', 'SectionExamGrade', obj.pk,
                field_name='score', old_value=old_score, new_value=obj.score,
            )
            _notify_staff_if_at_risk(gb)
            messages.success(request, 'Exam grade saved.')
            return redirect('staff_gradebook_detail', student_id=student.pk)
    else:
        form = SectionExamGradeForm(instance=instance)

    reset_warning = instance and instance.reset_count >= 2
    return render(request, 'grades/staff_exam_form.html', {
        'student': student, 'gb': gb, 'form': form, 'instance': instance, 'reset_warning': reset_warning,
    })


@staff_required
def staff_worksheet_edit(request, student_id, worksheet_id):
    student = get_object_or_404(Student, pk=student_id, role=Student.Role.STUDENT)
    gb, course = _get_or_none_gradebook(student)
    if not gb:
        messages.error(request, 'Create a gradebook for this student first.')
        return redirect('staff_gradebook_detail', student_id=student.pk)

    instance = None
    if worksheet_id != 'new':
        instance = get_object_or_404(WorksheetGrade, pk=worksheet_id, gradebook=gb)

    if request.method == 'POST':
        if gb.is_finalized:
            return HttpResponseForbidden('Gradebook is finalized')
        was_create = instance is None
        old_score = instance.score if instance else ''
        form = WorksheetGradeForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.gradebook = gb
            obj.entered_by = request.user
            obj.save()
            log_grade_change(
                gb, request.user, 'create' if was_create else 'update', 'WorksheetGrade', obj.pk,
                field_name='score', old_value=old_score, new_value=obj.score,
            )
            _notify_staff_if_at_risk(gb)
            messages.success(request, 'Worksheet grade saved.')
            return redirect('staff_gradebook_detail', student_id=student.pk)
    else:
        form = WorksheetGradeForm(instance=instance)

    return render(request, 'grades/staff_worksheet_form.html', {
        'student': student, 'gb': gb, 'form': form, 'instance': instance,
    })


@staff_required
def staff_skill_edit(request, student_id, skill_id):
    student = get_object_or_404(Student, pk=student_id, role=Student.Role.STUDENT)
    gb, course = _get_or_none_gradebook(student)
    if not gb:
        messages.error(request, 'Create a gradebook for this student first.')
        return redirect('staff_gradebook_detail', student_id=student.pk)

    instance = None
    if skill_id != 'new':
        instance = get_object_or_404(SkillsGrade, pk=skill_id, gradebook=gb)

    if request.method == 'POST':
        if gb.is_finalized:
            return HttpResponseForbidden('Gradebook is finalized')
        was_create = instance is None
        old_score = instance.score if instance else ''
        form = SkillsGradeForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.gradebook = gb
            obj.entered_by = request.user
            obj.save()
            log_grade_change(
                gb, request.user, 'create' if was_create else 'update', 'SkillsGrade', obj.pk,
                field_name='score', old_value=old_score, new_value=obj.score,
            )
            _notify_staff_if_at_risk(gb)
            messages.success(request, 'Skills grade saved.')
            return redirect('staff_gradebook_detail', student_id=student.pk)
    else:
        form = SkillsGradeForm(instance=instance)

    return render(request, 'grades/staff_skill_form.html', {
        'student': student, 'gb': gb, 'form': form, 'instance': instance,
    })


@staff_required
def staff_participation_deduct(request, student_id):
    student = get_object_or_404(Student, pk=student_id, role=Student.Role.STUDENT)
    gb, course = _get_or_none_gradebook(student)
    if not gb:
        messages.error(request, 'Create a gradebook for this student first.')
        return redirect('staff_gradebook_detail', student_id=student.pk)

    if request.method == 'POST':
        if gb.is_finalized:
            return HttpResponseForbidden('Gradebook is finalized')
        form = ParticipationDeductionForm(request.POST)
        if form.is_valid():
            old_participation = gb.participation_score
            obj = form.save(commit=False)
            obj.gradebook = gb
            obj.recorded_by = request.user
            obj.save()
            gb.refresh_from_db()
            log_grade_change(
                gb, request.user, 'create', 'ParticipationDeduction', obj.pk,
                field_name='participation_score', old_value=old_participation, new_value=gb.participation_score,
                notes=f'{obj.get_reason_display()} (-{obj.points})',
            )
            _notify_staff_if_at_risk(gb)
            messages.success(request, 'Deduction recorded.')
            return redirect('staff_gradebook_detail', student_id=student.pk)
    else:
        form = ParticipationDeductionForm()

    return render(request, 'grades/staff_participation_form.html', {
        'student': student, 'gb': gb, 'form': form,
    })


@staff_required
def finalize_gradebook(request, student_id):
    gradebook = get_object_or_404(GradeBook, student_id=student_id)
    if request.method == 'POST':
        gradebook.is_finalized = True
        gradebook.finalized_at = timezone.now()
        gradebook.finalized_by = request.user
        gradebook.finalized_notes = request.POST.get('notes', '')
        gradebook.save()
        log_grade_change(
            gradebook, request.user, 'update', 'GradeBook', gradebook.pk,
            field_name='is_finalized', old_value=False, new_value=True, notes='Gradebook finalized',
        )
        messages.success(request, f'Gradebook finalized for {gradebook.student.get_full_name()}.')
        return redirect('staff_gradebook_detail', student_id=student_id)
    return render(request, 'grades/finalize_confirm.html', {'gradebook': gradebook})


@staff_required
def unfinalize_gradebook(request, student_id):
    gradebook = get_object_or_404(GradeBook, student_id=student_id)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'A reason is required to unlock a finalized gradebook.')
            return redirect('staff_gradebook_detail', student_id=student_id)
        gradebook.is_finalized = False
        gradebook.finalized_at = None
        gradebook.finalized_by = None
        gradebook.finalized_notes = ''
        gradebook.save()
        log_grade_change(
            gradebook, request.user, 'update', 'GradeBook', gradebook.pk,
            field_name='is_finalized', old_value=True, new_value=False, notes=f'Unlocked: {reason}',
        )
        messages.success(request, 'Gradebook unlocked.')
    return redirect('staff_gradebook_detail', student_id=student_id)


@staff_required
def staff_grade_report(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    sort = request.GET.get('sort', 'name')

    enrollments = CourseEnrollment.objects.filter(course=course).select_related('student')
    rows = []
    for enrollment in enrollments:
        student = enrollment.student
        gb = GradeBook.objects.filter(student=student, course=course).first()
        rows.append({'student': student, 'gb': gb})

    if sort == 'grade':
        rows.sort(key=lambda r: (r['gb'].overall_grade if r['gb'] and r['gb'].overall_grade is not None else -1), reverse=True)
    elif sort == 'passing':
        rows.sort(key=lambda r: (r['gb'].is_passing if r['gb'] else False), reverse=True)
    else:
        rows.sort(key=lambda r: (r['student'].last_name, r['student'].first_name))

    passing_count = sum(1 for r in rows if r['gb'] and r['gb'].is_passing)
    graded_count = sum(1 for r in rows if r['gb'] and r['gb'].overall_grade is not None)
    pass_rate = round(passing_count / graded_count * 100, 1) if graded_count else None

    return render(request, 'grades/staff_class_report.html', {
        'course': course, 'rows': rows, 'sort': sort,
        'passing_count': passing_count, 'graded_count': graded_count, 'pass_rate': pass_rate,
    })


@staff_required
def staff_grade_report_csv(request, course_id):
    import csv
    course = get_object_or_404(Course, pk=course_id)
    enrollments = CourseEnrollment.objects.filter(course=course).select_related('student')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{course.name}_grades.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Student', 'Component 1 (30%)', 'Section Exams (40%)', 'Final Exam (30%)',
        'Overall Grade', 'Letter Grade', 'Passing', 'Meets Completion Requirements',
    ])
    for enrollment in enrollments:
        student = enrollment.student
        gb = GradeBook.objects.filter(student=student, course=course).first()
        writer.writerow([
            student.get_full_name(),
            gb.component_1_average if gb else '',
            gb.section_exam_average if gb else '',
            gb.final_exam_score if gb else '',
            gb.overall_grade if gb else '',
            gb.letter_grade if gb else '—',
            'Yes' if gb and gb.is_passing else 'No',
            'Yes' if gb and gb.meets_completion_requirements else 'No',
        ])
    return response


# ── Instructor views (read-only) ─────────────────────────────────────────────

@instructor_required
def instructor_grade_overview(request):
    instructor = request.user
    course_ids = InstructorCourseAssignment.objects.filter(
        instructor=instructor, is_active=True
    ).values_list('course_id', flat=True)

    rows = []
    for enrollment in CourseEnrollment.objects.filter(course_id__in=course_ids).select_related('student', 'course').order_by(
        'course__option_number', 'student__last_name'
    ):
        student = enrollment.student
        gb = GradeBook.objects.filter(student=student, course=enrollment.course).first()
        rows.append({'student': student, 'course': enrollment.course, 'gradebook': gb})

    return render(request, 'grades/instructor_overview.html', {'rows': rows})


@instructor_required
def instructor_gradebook_detail(request, student_id):
    instructor = request.user
    student = get_object_or_404(Student, pk=student_id, role=Student.Role.STUDENT)
    gb, course = _get_or_none_gradebook(student)

    # Only allow viewing students in this instructor's assigned courses
    if course:
        is_assigned = InstructorCourseAssignment.objects.filter(
            instructor=instructor, course=course, is_active=True
        ).exists()
        if not is_assigned:
            messages.error(request, 'You are not assigned to this student\'s course.')
            return redirect('instructor_grade_overview')

    return render(request, 'grades/instructor_gradebook_detail.html', {
        'student': student, 'course': course, 'gb': gb,
    })


# ── Student view (read-only, own gradebook) ───────────────────────────────────

@login_required
def student_grades_view(request):
    student = request.user
    gb, course = _get_or_none_gradebook(student)
    return render(request, 'grades/student_grades.html', {
        'course': course, 'gb': gb,
    })
