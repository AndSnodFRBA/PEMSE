from django.contrib import admin
from .models import StudentInvitation


@admin.register(StudentInvitation)
class StudentInvitationAdmin(admin.ModelAdmin):
    list_display  = ['email', 'created_by', 'created_at', 'expires_at', 'used', 'used_at']
    list_filter   = ['used']
    readonly_fields = ['token', 'created_at', 'used_at']
