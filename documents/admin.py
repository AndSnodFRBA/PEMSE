from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import DocumentType, StudentDocument


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display  = ['slug', 'label', 'required', 'order']
    list_editable = ['required', 'order']


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display  = ['student', 'doc_type', 'status', 'uploaded_at', 'reviewed_by', 'download_link']
    list_filter   = ['status', 'doc_type']
    search_fields = ['student__email', 'student__first_name', 'student__last_name']
    readonly_fields = ['uploaded_at', 'reviewed_at', 'file', 'download_link']
    actions = ['approve_docs', 'reject_docs']

    @admin.display(description='Download')
    def download_link(self, obj):
        if obj.file:
            try:
                url = obj.file.url  # pre-signed S3 URL or local path
                return format_html('<a href="{}" target="_blank">Download</a>', url)
            except Exception:
                return '—'
        return '—'

    def approve_docs(self, request, queryset):
        queryset.update(status='approved', reviewed_by=request.user, reviewed_at=timezone.now())
    approve_docs.short_description = 'Mark selected as Approved'

    def reject_docs(self, request, queryset):
        queryset.update(status='rejected', reviewed_by=request.user, reviewed_at=timezone.now())
    reject_docs.short_description = 'Mark selected as Rejected'
