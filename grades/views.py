from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.urls import reverse

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
    ParticipationDeductionForm, FisdapForm,
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
    return render(request, 'grades/staff_gradebook_detail.html', {
        'student': student,
        'course': course,
        'gb': gb,
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
        was_create = instance is None
        old_score = instance.score if instance else ''
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
        was_create = instance is None
        old_score = instance.score if instance else ''
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
            messages.success(request, 'Deduction recorded.')
            return redirect('staff_gradebook_detail', student_id=student.pk)
    else:
        form = ParticipationDeductionForm()

    return render(request, 'grades/staff_participation_form.html', {
        'student': student, 'gb': gb, 'form': form,
    })


@staff_required
def staff_fisdap_edit(request, student_id):
    student = get_object_or_404(Student, pk=student_id, role=Student.Role.STUDENT)
    gb, course = _get_or_none_gradebook(student)
    if not gb:
        messages.error(request, 'Create a gradebook for this student first.')
        return redirect('staff_gradebook_detail', student_id=student.pk)

    if request.method == 'POST':
        old_values = {
            'fisdap_attempt_1': gb.fisdap_attempt_1,
            'fisdap_attempt_2': gb.fisdap_attempt_2,
            'fisdap_passed': gb.fisdap_passed,
        }
        form = FisdapForm(request.POST, instance=gb)
        if form.is_valid():
            form.save()
            for field, old_val in old_values.items():
                new_val = getattr(gb, field)
                if old_val != new_val:
                    log_grade_change(
                        gb, request.user, 'update', 'GradeBook', gb.pk,
                        field_name=field, old_value=old_val, new_value=new_val,
                    )
            messages.success(request, 'FISDAP scores saved.')
            return redirect('staff_gradebook_detail', student_id=student.pk)
    else:
        form = FisdapForm(instance=gb)

    return render(request, 'grades/staff_fisdap_form.html', {
        'student': student, 'gb': gb, 'form': form,
    })


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
