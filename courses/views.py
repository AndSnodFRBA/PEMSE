from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Course, CourseEnrollment

@login_required
def course_list_view(request):
    courses = Course.objects.filter(is_active=True)
    enrollment = CourseEnrollment.objects.filter(student=request.user).first()
    return render(request, 'courses/course_list.html', {
        'courses': courses,
        'enrollment': enrollment,
    })

@login_required
def enroll_view(request, course_id):
    course = get_object_or_404(Course, pk=course_id, is_active=True)
    if request.method == 'POST':
        shirt_size = request.POST.get('shirt_size', '')
        enrollment, created = CourseEnrollment.objects.update_or_create(
            student=request.user,
            defaults={'course': course, 'shirt_size': shirt_size}
        )
        action = 'selected' if created else 'updated to'
        messages.success(request, f'Course {action}: {course.name}')
        return redirect('registration_form')
    return render(request, 'courses/enroll_confirm.html', {'course': course})
