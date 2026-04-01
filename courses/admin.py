from django.contrib import admin
from .models import Course, CourseEnrollment, CourseAnnouncement

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display  = ['option_number', 'tag', 'name', 'price', 'min_down', 'includes_shirt', 'is_active']
    list_editable = ['is_active', 'price', 'min_down']
    ordering      = ['option_number']

@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display  = ['student', 'course', 'shirt_size', 'enrolled_at']
    list_filter   = ['course']
    search_fields = ['student__email', 'student__first_name', 'student__last_name']

@admin.register(CourseAnnouncement)
class CourseAnnouncementAdmin(admin.ModelAdmin):
    list_display  = ['course', 'title', 'is_active', 'created_at']
    list_filter   = ['course', 'is_active']
