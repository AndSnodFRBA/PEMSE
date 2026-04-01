from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class Student(AbstractUser):
    """Custom user model — one row = one enrolled student."""

    # ── Contact ───────────────────────────────────────────────────────────────
    phone       = models.CharField(max_length=20, blank=True)
    ok_to_text  = models.BooleanField(null=True, blank=True)
    address     = models.CharField(max_length=200, blank=True)
    city        = models.CharField(max_length=100, blank=True)
    state       = models.CharField(max_length=2, blank=True)
    zip_code    = models.CharField(max_length=10, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    # ── Enrollment status ─────────────────────────────────────────────────────
    class EnrollStatus(models.TextChoices):
        PENDING   = 'pending',   'Pending review'
        ACTIVE    = 'active',    'Active'
        COMPLETE  = 'complete',  'Course complete'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    enroll_status = models.CharField(
        max_length=20, choices=EnrollStatus.choices,
        default=EnrollStatus.PENDING
    )
    reg_submitted    = models.BooleanField(default=False)
    reg_submitted_at = models.DateTimeField(null=True, blank=True)
    reg_conf_number  = models.CharField(max_length=30, blank=True)

    # ── Signatures ────────────────────────────────────────────────────────────
    contract_signed     = models.BooleanField(default=False)
    contract_sig_name   = models.CharField(max_length=200, blank=True)
    contract_signed_at  = models.DateTimeField(null=True, blank=True)

    handbook_signed     = models.BooleanField(default=False)
    handbook_sig_name   = models.CharField(max_length=200, blank=True)
    handbook_signed_at  = models.DateTimeField(null=True, blank=True)

    # ── Shirt (AEMT courses) ──────────────────────────────────────────────────
    shirt_size = models.CharField(max_length=10, blank=True)

    class Meta:
        verbose_name = 'Student'
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.get_full_name()} ({self.email})'

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.email

    @property
    def initials(self):
        parts = self.get_full_name().split()
        return ''.join(p[0].upper() for p in parts[:2]) if parts else '?'

    @property
    def enrollment_complete(self):
        from documents.models import StudentDocument
        docs_ok = StudentDocument.objects.filter(
            student=self, doc_type__required=True
        ).count() >= 3  # DL, CPR, Immunizations
        return (self.reg_submitted and self.handbook_signed
                and self.contract_signed and docs_ok)


class PaymentRecord(models.Model):
    """Tracks payment method and schedule for a student."""

    class Method(models.TextChoices):
        CASH  = 'cash',  'Cash'
        CHECK = 'check', 'Check'
        DEPT  = 'dept',  'Department paying'

    class Option(models.TextChoices):
        FULL     = 'full',     'Pay in full'
        SCHEDULE = 'schedule', 'Payment schedule'

    student     = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='payment')
    method      = models.CharField(max_length=10, choices=Method.choices, blank=True)
    pay_option  = models.CharField(max_length=10, choices=Option.choices, blank=True)
    check_number = models.CharField(max_length=50, blank=True)

    # Department billing
    dept_name    = models.CharField(max_length=200, blank=True)
    dept_address = models.TextField(blank=True)
    dept_contact = models.CharField(max_length=200, blank=True)
    dept_email   = models.EmailField(blank=True)
    dept_phone   = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.student} — {self.get_method_display()}'


class Announcement(models.Model):
    """Admin-posted announcements shown on student dashboards."""
    title      = models.CharField(max_length=200)
    body       = models.TextField()
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        Student, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='announcements_created'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
