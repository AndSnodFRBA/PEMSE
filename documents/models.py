import os
from django.db import models
from django.conf import settings


def student_document_path(instance, filename):
    """Upload to: student-documents/<student_id>/<doc_type>/<filename>"""
    ext = os.path.splitext(filename)[1].lower()
    safe_name = f'{instance.doc_type.slug}{ext}'
    return f'student-documents/{instance.student.id}/{instance.doc_type.slug}/{safe_name}'


def instructor_document_path(instance, filename):
    """Upload to: instructor-documents/<uploader_id>/<filename>"""
    return f'instructor-documents/{instance.uploaded_by_id}/{filename}'


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
    expiration_date = models.DateField(null=True, blank=True, help_text='Expiration date for CPR cards and licenses')
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

    @property
    def expiration_warning(self):
        """'expired' or 'expiring_soon' (within 90 days) if this document has an expiration_date, else None."""
        if not self.expiration_date:
            return None
        from django.utils import timezone
        days = (self.expiration_date - timezone.now().date()).days
        if days < 0:
            return 'expired'
        if days <= 90:
            return 'expiring_soon'
        return None


class InstructorDocument(models.Model):
    """A file uploaded by staff/an instructor for students to view — handbook, class materials, forms."""
    title       = models.CharField(max_length=200)
    description = models.CharField(max_length=300, blank=True)
    file        = models.FileField(upload_to=instructor_document_path)
    course      = models.ForeignKey(
        'courses.Course', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='instructor_documents',
        help_text='Leave blank to show to all students, regardless of course.',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='documents_uploaded'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ''
