import os
from django.db import models
from django.conf import settings


def student_document_path(instance, filename):
    """Upload to: documents/<student_id>/<doc_type>/<filename>"""
    ext = os.path.splitext(filename)[1].lower()
    safe_name = f'{instance.doc_type.slug}{ext}'
    return f'documents/{instance.student.id}/{instance.doc_type.slug}/{safe_name}'


class DocumentType(models.Model):
    """Defines the types of documents students must upload."""
    slug        = models.SlugField(unique=True)
    label       = models.CharField(max_length=200)
    hint        = models.CharField(max_length=300, blank=True)
    required    = models.BooleanField(default=True)
    icon_color  = models.CharField(max_length=7, default='#854f0b')
    icon_bg     = models.CharField(max_length=7, default='#faeeda')
    order       = models.PositiveIntegerField(default=0)

    ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png']

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.label


class StudentDocument(models.Model):
    """A file uploaded by a student for a specific document type."""

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected — re-upload required'

    student  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    doc_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT, related_name='uploads')
    file     = models.FileField(upload_to=student_document_path)
    status   = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes    = models.TextField(blank=True, help_text='Admin notes (rejection reason, etc.)')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='docs_reviewed'
    )

    class Meta:
        unique_together = [['student', 'doc_type']]  # one file per doc type per student
        ordering = ['doc_type__order']

    def __str__(self):
        return f'{self.student} — {self.doc_type}'

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ''

    @property
    def status_color(self):
        return {'pending': '#d4a017', 'approved': '#0a7a4b', 'rejected': '#c8102e'}.get(self.status, '#888')
