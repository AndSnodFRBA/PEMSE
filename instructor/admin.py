from django.contrib import admin
from .models import (
    InstructorCourseAssignment,
    InstructionalHourLog,
    AttendanceRecord,
    StudentAttendance,
    InstructorObservation,
    InstructorMeeting,
    RemediationPlan,
    InstructorNote,
)


@admin.register(InstructorCourseAssignment)
class InstructorCourseAssignmentAdmin(admin.ModelAdmin):
    list_display = ['instructor', 'course', 'role', 'is_active', 'assigned_at']
    list_filter  = ['role', 'is_active', 'course']
    search_fields = ['instructor__first_name', 'instructor__last_name', 'course__name']
    raw_id_fields = ['instructor', 'assigned_by']


@admin.register(InstructionalHourLog)
class InstructionalHourLogAdmin(admin.ModelAdmin):
    list_display  = ['instructor', 'course', 'session_date', 'session_type', 'hours', 'verified']
    list_filter   = ['session_type', 'verified', 'course']
    search_fields = ['instructor__first_name', 'instructor__last_name', 'topic_covered']
    date_hierarchy = 'session_date'
    raw_id_fields = ['instructor', 'verified_by']


class StudentAttendanceInline(admin.TabularInline):
    model = StudentAttendance
    extra = 0
    raw_id_fields = ['student']


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display  = ['course', 'session_date', 'session_type', 'instructor']
    list_filter   = ['session_type', 'course']
    date_hierarchy = 'session_date'
    inlines       = [StudentAttendanceInline]
    raw_id_fields = ['instructor']


@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display  = ['student', 'session', 'status']
    list_filter   = ['status']
    raw_id_fields = ['student']


@admin.register(InstructorObservation)
class InstructorObservationAdmin(admin.ModelAdmin):
    list_display  = ['instructor', 'observation_date', 'overall_rating', 'instructor_acknowledged']
    list_filter   = ['instructor_acknowledged']
    date_hierarchy = 'observation_date'
    raw_id_fields = ['instructor', 'observed_by']


@admin.register(InstructorMeeting)
class InstructorMeetingAdmin(admin.ModelAdmin):
    list_display  = ['instructor', 'meeting_date', 'meeting_type', 'instructor_acknowledged']
    list_filter   = ['meeting_type', 'instructor_acknowledged']
    date_hierarchy = 'meeting_date'
    raw_id_fields = ['instructor', 'conducted_by']


@admin.register(RemediationPlan)
class RemediationPlanAdmin(admin.ModelAdmin):
    list_display  = ['instructor', 'created_date', 'status', 'target_date', 'instructor_acknowledged']
    list_filter   = ['status']
    raw_id_fields = ['instructor', 'created_by']


@admin.register(InstructorNote)
class InstructorNoteAdmin(admin.ModelAdmin):
    list_display  = ['instructor', 'student', 'course', 'created_at']
    raw_id_fields = ['instructor', 'student']
