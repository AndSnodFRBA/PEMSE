import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class StudentInvitation(models.Model):
    """A one-time email invitation that lets a student self-register."""

    email      = models.EmailField()
    course     = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invitations',
    )
    token      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invitations_sent',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used       = models.BooleanField(default=False)
    used_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.used and not self.is_expired

    def __str__(self):
        status = 'used' if self.used else ('expired' if self.is_expired else 'pending')
        return f'Invite → {self.email} ({status})'


class StaffInvitation(models.Model):
    """A one-time email invitation that lets a new office staff member set up their own account."""

    email      = models.EmailField()
    token      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='staff_invitations_sent',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used       = models.BooleanField(default=False)
    used_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.used and not self.is_expired

    def __str__(self):
        status = 'used' if self.used else ('expired' if self.is_expired else 'pending')
        return f'Staff invite → {self.email} ({status})'


class InstructorInvitation(models.Model):
    """A one-time email invitation that lets a new instructor set up their own profile."""

    email      = models.EmailField()
    token      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='instructor_invitations_sent',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used       = models.BooleanField(default=False)
    used_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.used and not self.is_expired

    def __str__(self):
        status = 'used' if self.used else ('expired' if self.is_expired else 'pending')
        return f'Instructor invite → {self.email} ({status})'


class MedicalDirectorConsultation(models.Model):
    """Program director's log of required contact with the medical director.
    Visible to the program director (Admin role) only — not shown to office staff."""

    CONSULTATION_TYPES = [
        ('routine',   'Routine Check-In'),
        ('protocol',  'Protocol Review'),
        ('qa_case',   'QA / Case Review'),
        ('incident',  'Incident Review'),
        ('other',     'Other'),
    ]

    conducted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='medical_director_consultations',
    )
    medical_director_name = models.CharField(max_length=200, blank=True)
    consultation_date     = models.DateField()
    consultation_type     = models.CharField(max_length=20, choices=CONSULTATION_TYPES, default='routine')
    topics_discussed      = models.TextField()
    action_items          = models.TextField(blank=True)
    next_consultation_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-consultation_date']

    def __str__(self):
        return f'{self.get_consultation_type_display()} — {self.consultation_date}'
