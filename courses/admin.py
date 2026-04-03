from django.contrib import admin
from .models import Course, CourseEnrollment, CourseAnnouncement


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display  = [
        'option_number', 'tag', 'licensure', 'name', 'price', 'min_down',
        'includes_shirt', 'start_date', 'registration_close_date', 'max_students', 'is_active',
    ]
    list_editable = ['is_active', 'price', 'min_down']
    ordering      = ['option_number']
    fieldsets = [
        ('Basic Info', {
            'fields': ['option_number', 'tag', 'tag_color', 'tag_bg', 'name', 'description',
                       'licensure', 'price', 'min_down', 'includes_shirt', 'is_active', 'order'],
        }),
        ('Location', {
            'fields': ['location_name', 'location_address', 'location_city', 'location_state'],
        }),
        ('Dates & Capacity', {
            'fields': ['start_date', 'end_date', 'registration_close_date', 'max_students'],
        }),
        ('Schedule', {
            'fields': ['schedule_notes'],
        }),
    ]


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display  = ['student', 'course', 'shirt_size', 'enrolled_at']
    list_filter   = ['course']
    search_fields = ['student__email', 'student__first_name', 'student__last_name']


@admin.register(CourseAnnouncement)
class CourseAnnouncementAdmin(admin.ModelAdmin):
    list_display  = ['course', 'title', 'is_active', 'created_at']
    list_filter   = ['course', 'is_active']
