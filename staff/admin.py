from django.contrib import admin
from .models import MedicalDirectorConsultation, StaffInvitation, StudentInvitation


@admin.register(StudentInvitation)
class StudentInvitationAdmin(admin.ModelAdmin):
    list_display  = ['email', 'course', 'created_by', 'created_at', 'expires_at', 'used', 'used_at']
    list_filter   = ['used', 'course']
    readonly_fields = ['token', 'created_at', 'used_at']


@admin.register(StaffInvitation)
class StaffInvitationAdmin(admin.ModelAdmin):
    list_display  = ['email', 'created_by', 'created_at', 'expires_at', 'used', 'used_at']
    list_filter   = ['used']
    readonly_fields = ['token', 'created_at', 'used_at']


@admin.register(MedicalDirectorConsultation)
class MedicalDirectorConsultationAdmin(admin.ModelAdmin):
    list_display  = ['consultation_date', 'consultation_type', 'medical_director_name', 'conducted_by']
    list_filter   = ['consultation_type', 'consultation_date']
    date_hierarchy = 'consultation_date'
