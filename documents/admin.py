from django.contrib import admin
from django.utils import timezone
from .models import DocumentType, StudentDocument


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display  = ['slug', 'label', 'required', 'order']
    list_editable = ['required', 'order']


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display  = ['student', 'doc_type', 'status', 'uploaded_at', 'reviewed_by']
    list_filter   = ['status', 'doc_type']
    search_fields = ['student__email', 'student__first_name', 'student__last_name']
    readonly_fields = ['uploaded_at', 'reviewed_at', 'file']
    actions = ['approve_docs', 'reject_docs']

    def approve_docs(self, request, queryset):
        queryset.update(status='approved', reviewed_by=request.user, reviewed_at=timezone.now())
    approve_docs.short_description = 'Mark selected as Approved'

    def reject_docs(self, request, queryset):
        queryset.update(status='rejected', reviewed_by=request.user, reviewed_at=timezone.now())
    reject_docs.short_description = 'Mark selected as Rejected'
