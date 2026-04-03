from django.db import models
from django.conf import settings


class Course(models.Model):
    """PEMSE course offering — mirrors the 7 options on the 2025 registration form."""

    SHIRT_REQUIRED_TAG = 'AEMT'

    class Licensure(models.TextChoices):
        EMR   = 'EMR',   'Emergency Medical Responder (EMR)'
        EMT   = 'EMT',   'Emergency Medical Technician (EMT)'
        AEMT  = 'AEMT',  'Advanced EMT (AEMT)'
        PARA  = 'PARA',  'Paramedic'
        CE    = 'CE',    'Continuing Education'
        OTHER = 'OTHER', 'Other'

    option_number  = models.PositiveIntegerField(unique=True)
    tag            = models.CharField(max_length=20)   # EMR, EMT, AEMT, Bridge, CE
    tag_color      = models.CharField(max_length=7, default='#0a6b47')
    tag_bg         = models.CharField(max_length=7, default='#d8f5ec')
    name           = models.CharField(max_length=200)
    description    = models.TextField(blank=True)
    price          = models.DecimalField(max_digits=8, decimal_places=2)
    min_down       = models.DecimalField(max_digits=8, decimal_places=2)
    includes_shirt = models.BooleanField(default=False)
    is_active      = models.BooleanField(default=True)
    order          = models.PositiveIntegerField(default=0)

    # ── Location ──────────────────────────────────────────────────────────────
    location_name    = models.CharField(max_length=200, blank=True, help_text='e.g. Scottsbluff Fire Station 1')
    location_address = models.CharField(max_length=300, blank=True)
    location_city    = models.CharField(max_length=100, blank=True)
    location_state   = models.CharField(max_length=2, blank=True, default='NE')

    # ── Licensure level ───────────────────────────────────────────────────────
    licensure = models.CharField(max_length=10, choices=Licensure.choices, blank=True)

    # ── Dates ─────────────────────────────────────────────────────────────────
    start_date              = models.DateField(null=True, blank=True)
    end_date                = models.DateField(null=True, blank=True)
    registration_close_date = models.DateField(
        null=True, blank=True,
        help_text='Course disappears from registration page after this date',
    )

    # ── Capacity ──────────────────────────────────────────────────────────────
    max_students = models.PositiveIntegerField(
        null=True, blank=True, help_text='Leave blank for unlimited',
    )

    # ── Schedule ──────────────────────────────────────────────────────────────
    schedule_notes = models.TextField(blank=True, help_text='e.g. Mondays and Wednesdays 6-10pm')

    class Meta:
        ordering = ['order', 'option_number']

    def __str__(self):
        return f'Option {self.option_number} — {self.name} (${self.price})'

    @property
    def remaining_balance(self):
        return self.price - self.min_down

    @property
    def registration_open(self):
        from django.utils import timezone
        today = timezone.now().date()
        if self.registration_close_date and today > self.registration_close_date:
            return False
        if self.max_students:
            enrolled = self.enrollments.count()
            if enrolled >= self.max_students:
                return False
        return self.is_active

    @property
    def spots_remaining(self):
        if not self.max_students:
            return None
        return max(0, self.max_students - self.enrollments.count())

    @property
    def location_display(self):
        parts = [p for p in [self.location_name, self.location_city] if p]
        return ', '.join(parts) if parts else ''


class CourseEnrollment(models.Model):
    """Links a Student to the Course they selected."""

    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollment'
    )
    course      = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='enrollments')
    shirt_size  = models.CharField(max_length=10, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.student} → {self.course}'


class CourseAnnouncement(models.Model):
    """Course-specific announcement (e.g. start dates, schedule changes)."""
    course     = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='course_announcements')
    title      = models.CharField(max_length=200)
    body       = models.TextField()
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.course.tag}] {self.title}'
