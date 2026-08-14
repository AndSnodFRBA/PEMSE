import os
import uuid

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


def profile_photo_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f'profile-photos/{instance.pk}/photo{ext}'


class Student(AbstractUser):
    """Custom user model — one row = one enrolled student or staff member."""

    class Role(models.TextChoices):
        STUDENT    = 'student',    'Student'
        INSTRUCTOR = 'instructor', 'Instructor'
        STAFF      = 'staff',      'Office Staff'
        ADMIN      = 'admin',      'Administrator'

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.STUDENT,
    )

    # ── Contact ───────────────────────────────────────────────────────────────
    phone       = models.CharField(max_length=20, blank=True)
    ok_to_text  = models.BooleanField(null=True, blank=True)
    address     = models.CharField(max_length=200, blank=True)
    city        = models.CharField(max_length=100, blank=True)
    state       = models.CharField(max_length=2, blank=True)
    zip_code    = models.CharField(max_length=10, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_photo = models.ImageField(
        upload_to=profile_photo_path,
        null=True, blank=True,
        help_text='Optional profile photo. Helps instructors learn student names.'
    )

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

    # ── Signatures (stores base64 PNG data from canvas pad) ───────────────────
    contract_signed     = models.BooleanField(default=False)
    contract_sig_name   = models.TextField(blank=True)
    contract_signed_at  = models.DateTimeField(null=True, blank=True)

    handbook_signed     = models.BooleanField(default=False)
    handbook_sig_name   = models.TextField(blank=True)
    handbook_signed_at  = models.DateTimeField(null=True, blank=True)

    # ── Shirt (AEMT courses) ──────────────────────────────────────────────────
    shirt_size = models.CharField(max_length=10, blank=True)

    # ── Instructor profile ────────────────────────────────────────────────────
    instructor_license_number   = models.CharField(max_length=100, blank=True)
    instructor_license_level    = models.CharField(max_length=50, blank=True, choices=[
        ('EMR',       'EMR Instructor'),
        ('EMT',       'EMT Instructor'),
        ('AEMT',      'AEMT Instructor'),
        ('Paramedic', 'Paramedic Instructor'),
    ])
    instructor_license_expiry   = models.DateField(null=True, blank=True)
    instructor_certifications   = models.TextField(blank=True, help_text='Additional certifications, comma-separated')
    instructor_bio              = models.TextField(blank=True)
    instructor_employer         = models.CharField(max_length=200, blank=True)
    instructor_employer_address = models.CharField(max_length=300, blank=True)
    instructor_years_experience = models.PositiveIntegerField(null=True, blank=True)
    instructor_primary          = models.BooleanField(default=False, help_text='Primary instructor for a course')

    # ── Calendar subscription ─────────────────────────────────────────────────
    calendar_token = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        help_text='Secret token used in the ICS feed URL for phone calendar subscriptions',
    )

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
    def is_office_staff(self):
        return self.role in (self.Role.STAFF, self.Role.ADMIN) or self.is_superuser or self.is_staff

    @property
    def is_instructor(self):
        return self.role == self.Role.INSTRUCTOR

    @property
    def calendar_courses(self):
        """Courses this user's calendar page/ICS feed should include events for."""
        from courses.models import Course, CourseEnrollment
        if self.is_office_staff:
            return Course.objects.all()
        if self.is_instructor:
            from instructor.models import InstructorCourseAssignment
            course_ids = InstructorCourseAssignment.objects.filter(
                instructor=self, is_active=True
            ).values_list('course_id', flat=True)
            return Course.objects.filter(pk__in=course_ids)
        course_ids = CourseEnrollment.objects.filter(student=self).values_list('course_id', flat=True)
        return Course.objects.filter(pk__in=course_ids)

    @property
    def enrollment_complete(self):
        from documents.models import StudentDocument, DocumentType
        required_count = DocumentType.objects.filter(required=True).count()
        docs_ok = StudentDocument.objects.filter(
            student=self,
            doc_type__required=True,
            status='approved',
        ).count() >= required_count
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


class PaymentHistory(models.Model):
    """Individual payment installments recorded by staff."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payment_history')
    amount  = models.DecimalField(max_digits=8, decimal_places=2)
    payment_date = models.DateField()
    method  = models.CharField(max_length=20, choices=[
        ('cash',  'Cash'),
        ('check', 'Check'),
        ('card',  'Card'),
        ('dept',  'Department'),
    ])
    check_number = models.CharField(max_length=50, blank=True)
    notes        = models.TextField(blank=True)
    recorded_by  = models.ForeignKey(
        Student, null=True, on_delete=models.SET_NULL, related_name='payments_recorded'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f'{self.student} — ${self.amount} on {self.payment_date}'


class LatePaymentFee(models.Model):
    """Tracks late/collections fees per handbook policy ($25/month, $50 collections)."""

    class FeeType(models.TextChoices):
        MONTHLY_LATE  = 'monthly_late',  'Monthly late fee ($25)'
        COLLECTIONS   = 'collections',   'Collections fee ($50)'
        OTHER         = 'other',         'Other'

    FEE_AMOUNTS = {
        'monthly_late': 25,
        'collections':  50,
    }

    student     = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='late_fees')
    fee_type    = models.CharField(max_length=20, choices=FeeType.choices)
    amount      = models.DecimalField(max_digits=8, decimal_places=2)
    date_applied = models.DateField()
    reason      = models.TextField(blank=True)
    waived      = models.BooleanField(default=False)
    waived_by   = models.ForeignKey(
        Student, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='fees_waived'
    )
    waived_reason = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        Student, null=True, on_delete=models.SET_NULL, related_name='fees_recorded'
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_applied']

    def __str__(self):
        return f'{self.student} — {self.get_fee_type_display()} ({self.date_applied})'

    @property
    def is_active(self):
        return not self.waived


class ReminderLog(models.Model):
    """One row per reminder email actually sent — powers cooldown checks and staff-visible history."""

    class Channel(models.TextChoices):
        AUTO   = 'auto',   'Automated'
        MANUAL = 'manual', 'Staff bulk send'

    student  = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='reminder_logs')
    rule_key = models.CharField(max_length=50)
    channel  = models.CharField(max_length=10, choices=Channel.choices, default=Channel.AUTO)
    course   = models.ForeignKey(
        'courses.Course', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reminder_logs',
    )
    sent_by  = models.ForeignKey(
        Student, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reminders_sent',
    )
    subject  = models.CharField(max_length=200)
    body     = models.TextField(blank=True)
    sent_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [models.Index(fields=['student', 'rule_key', 'sent_at'])]

    def __str__(self):
        return f'{self.student} — {self.rule_key} ({self.sent_at:%Y-%m-%d})'


class StudentNote(models.Model):
    """Free-form staff notes about a student — communications, general notes, etc."""

    class NoteType(models.TextChoices):
        COMMUNICATION = 'communication', 'Communication'
        GENERAL       = 'general',       'General'
        OTHER         = 'other',         'Other'

    student    = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='notes')
    note_type  = models.CharField(max_length=20, choices=NoteType.choices, default=NoteType.GENERAL)
    body       = models.TextField()
    created_by = models.ForeignKey(
        Student, null=True, on_delete=models.SET_NULL, related_name='notes_authored'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student} — {self.get_note_type_display()} ({self.created_at:%Y-%m-%d})'


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
    publish_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Leave blank to publish immediately. Set a future date/time to schedule.'
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Optional. Announcement automatically hides after this date/time.'
    )
    course = models.ForeignKey(
        'courses.Course',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='announcements',
        help_text='Leave blank to show to all students. Select a course to show only to that course enrollment.'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def schedule_status(self):
        """'scheduled' / 'live' / 'expired' — for the staff announcements list."""
        now = timezone.now()
        if self.publish_at and self.publish_at > now:
            return 'scheduled'
        if self.expires_at and self.expires_at < now:
            return 'expired'
        return 'live'


class StudentNotification(models.Model):
    """In-portal notification bell items for students."""

    class NotificationType(models.TextChoices):
        DOCUMENT_APPROVED  = 'doc_approved',  'Document approved'
        DOCUMENT_REJECTED  = 'doc_rejected',  'Document rejected'
        PAYMENT_RECORDED   = 'payment',       'Payment recorded'
        ANNOUNCEMENT       = 'announcement',  'New announcement'
        DEADLINE_REMINDER  = 'deadline',      'Upcoming deadline'
        EVAL_REQUESTED     = 'eval_request',  'Evaluation requested'
        GENERAL            = 'general',       'General'

    student     = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='notifications')
    notif_type  = models.CharField(max_length=20, choices=NotificationType.choices)
    title       = models.CharField(max_length=200)
    body        = models.TextField(blank=True)
    link        = models.CharField(max_length=300, blank=True, help_text='URL to link to')
    is_read     = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student} — {self.title}'

    @classmethod
    def create(cls, student, notif_type, title, body='', link=''):
        return cls.objects.create(
            student=student,
            notif_type=notif_type,
            title=title,
            body=body,
            link=link,
        )


# ── 172 NAC Chapter 13 Compliance Records ────────────────────────────────────

class CognitiveExamRecord(models.Model):
    """Per 172 NAC 13-004(B)(i)(2) — Grades for each cognitive examination."""
    student       = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='cognitive_exams')
    course        = models.ForeignKey('courses.Course', on_delete=models.CASCADE)
    exam_name     = models.CharField(max_length=200)
    exam_date     = models.DateField()
    score         = models.DecimalField(max_digits=5, decimal_places=2)
    passed        = models.BooleanField()
    attempt_number = models.PositiveIntegerField(default=1)
    notes         = models.TextField(blank=True)
    recorded_by   = models.ForeignKey(
        Student, null=True, on_delete=models.SET_NULL, related_name='exams_recorded'
    )
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['exam_date', 'attempt_number']

    def __str__(self):
        return f'{self.student.get_full_name()} — {self.exam_name} ({self.exam_date})'


class PsychomotorSkillRecord(models.Model):
    """Per 172 NAC 13-004(B)(i)(3) — Psychomotor skill evaluations."""
    student                  = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='psychomotor_skills')
    course                   = models.ForeignKey('courses.Course', on_delete=models.CASCADE)
    skill_name               = models.CharField(max_length=200)
    evaluation_date          = models.DateField()
    passed                   = models.BooleanField()
    attempt_number           = models.PositiveIntegerField(default=1)
    evaluator_name           = models.CharField(max_length=200)
    evaluator_qualifications = models.CharField(max_length=200, blank=True)
    notes                    = models.TextField(blank=True)
    recorded_by              = models.ForeignKey(
        Student, null=True, on_delete=models.SET_NULL, related_name='skills_recorded'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['evaluation_date']

    def __str__(self):
        return f'{self.student.get_full_name()} — {self.skill_name} ({self.evaluation_date})'


class PatientContactRecord(models.Model):
    """Per 172 NAC 13-004(B)(i)(4) — Patient contacts and AEMT-specific procedures."""
    student      = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='patient_contacts_rec')
    course       = models.ForeignKey('courses.Course', on_delete=models.CASCADE)
    contact_date = models.DateField()
    site_name    = models.CharField(max_length=200)
    contact_type = models.CharField(max_length=50, choices=[
        ('field',      'Field Experience'),
        ('clinical',   'Clinical Training'),
        ('simulated',  'Simulated Patient Encounter'),
        ('ed',         'Emergency Department'),
        ('other',      'Other'),
    ])
    supervisor_name          = models.CharField(max_length=200)
    supervisor_license_level = models.CharField(max_length=50, blank=True)
    patient_age_group        = models.CharField(max_length=20, choices=[
        ('adult',      'Adult'),
        ('pediatric',  'Pediatric'),
        ('geriatric',  'Geriatric'),
        ('obstetric',  'Obstetric'),
    ], blank=True)
    chief_complaint = models.CharField(max_length=200, blank=True)
    # AEMT specific per 172 NAC 13-004(B)(i)(6)(7)
    iv_start_attempted       = models.BooleanField(default=False)
    iv_start_successful      = models.BooleanField(default=False)
    airway_placement_attempted  = models.BooleanField(default=False)
    airway_placement_successful = models.BooleanField(default=False)
    notes      = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-contact_date']

    def __str__(self):
        return f'{self.student.get_full_name()} — {self.site_name} ({self.contact_date})'


class EntranceRequirementRecord(models.Model):
    """Per 172 NAC 13-004(B)(i)(8) — Copy of each student's entrance requirements."""
    student          = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='entrance_requirements')
    course           = models.ForeignKey('courses.Course', on_delete=models.CASCADE)
    requirement_name = models.CharField(max_length=200)
    verified         = models.BooleanField(default=False)
    verified_date    = models.DateField(null=True, blank=True)
    verified_by      = models.ForeignKey(
        Student, null=True, on_delete=models.SET_NULL, related_name='requirements_verified'
    )
    document_on_file = models.BooleanField(default=False)
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['requirement_name']

    def __str__(self):
        return f'{self.student.get_full_name()} — {self.requirement_name}'


class CourseCompletionRecord(models.Model):
    """Per 172 NAC 13-004(A) — Official verification of course completion."""
    student  = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='completion_records')
    course   = models.ForeignKey('courses.Course', on_delete=models.CASCADE)
    # Completion or withdrawal
    completion_date  = models.DateField(null=True, blank=True)
    withdrew         = models.BooleanField(default=False)
    withdrawal_date  = models.DateField(null=True, blank=True)
    withdrawal_reason = models.TextField(blank=True)
    # Hours per 172 NAC 13-004(A)(vi)
    total_hours            = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    didactic_hours         = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    clinical_hours         = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    field_internship_hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    # Official verification per 172 NAC 13-004(A)(i)(ii)
    verified_by_name   = models.CharField(max_length=200, blank=True)
    verified_by_title  = models.CharField(max_length=200, blank=True)
    verification_date  = models.DateField(null=True, blank=True)
    certificate_issued      = models.BooleanField(default=False)
    certificate_issued_date = models.DateField(null=True, blank=True)
    nremt_eligibility_sent  = models.BooleanField(default=False)
    nremt_eligibility_date  = models.DateField(null=True, blank=True)
    # NREMT exam outcomes per 172 NAC 13-004(A)
    class NREMTResult(models.TextChoices):
        PASS      = 'pass',      'Pass'
        FAIL      = 'fail',      'Fail'
        PENDING   = 'pending',   'Pending'
        NOT_TAKEN = 'not_taken', 'Not taken'
    nremt_cognitive_result   = models.CharField(
        max_length=10, choices=NREMTResult.choices, default=NREMTResult.NOT_TAKEN, blank=True
    )
    nremt_cognitive_date     = models.DateField(null=True, blank=True)
    nremt_cognitive_attempts = models.PositiveSmallIntegerField(default=0)
    nremt_psychomotor_result = models.CharField(
        max_length=10, choices=NREMTResult.choices, default=NREMTResult.NOT_TAKEN, blank=True
    )
    nremt_psychomotor_date   = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Retention per 172 NAC 13-004(F)(iii)
    retain_until = models.DateField(
        null=True, blank=True,
        help_text='Records must be retained minimum 5 years per 172 NAC Chapter 13. Auto-set on completion.'
    )
    records_flagged_for_review = models.BooleanField(
        default=False,
        help_text='Flag when retention period is ending and records should be reviewed before deletion'
    )

    class Meta:
        unique_together = [['student', 'course']]

    def save(self, *args, **kwargs):
        if self.completion_date and not self.retain_until:
            try:
                self.retain_until = self.completion_date.replace(year=self.completion_date.year + 5)
            except ValueError:
                # Feb 29 on a source year whose +5 target isn't a leap year
                self.retain_until = self.completion_date.replace(month=2, day=28, year=self.completion_date.year + 5)
        super().save(*args, **kwargs)

    def __str__(self):
        status = 'Completed' if self.completion_date else ('Withdrew' if self.withdrew else 'In progress')
        return f'{self.student.get_full_name()} — {self.course.name} ({status})'


class CourseReportRecord(models.Model):
    """Per 172 NAC 13-004(D) — Submit to Department within 30 days of course completion."""
    course                = models.OneToOneField(
        'courses.Course', on_delete=models.CASCADE, related_name='department_report'
    )
    training_agency_name  = models.CharField(max_length=200, default='Panhandle EMS Education')
    course_location       = models.CharField(max_length=300)
    instructor_names      = models.TextField(help_text='Names of all instructors for this course')
    students_enrolled     = models.PositiveIntegerField(default=0)
    students_withdrew     = models.PositiveIntegerField(default=0)
    students_completed    = models.PositiveIntegerField(default=0)
    total_didactic_hours  = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    total_clinical_hours  = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    total_field_hours     = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    report_submitted_to_department = models.BooleanField(default=False)
    report_submitted_date = models.DateField(null=True, blank=True)
    submission_deadline   = models.DateField(
        null=True, blank=True, help_text='30 days after course completion'
    )
    notes      = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Dept. Report — {self.course.name}'

    @property
    def pass_rate(self):
        if not self.students_enrolled:
            return None
        return round(self.students_completed / self.students_enrolled * 100, 1)

    @property
    def is_overdue(self):
        if self.report_submitted_to_department:
            return False
        if not self.submission_deadline:
            return False
        from django.utils import timezone
        return timezone.now().date() > self.submission_deadline

    @property
    def deadline_soon(self):
        """True if deadline is within 7 days and not yet submitted."""
        if self.report_submitted_to_department or not self.submission_deadline:
            return False
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now().date() >= self.submission_deadline - timedelta(days=7)


class WebhookLog(models.Model):
    """Records each run of the /webhooks/daily-tasks/ endpoint."""

    triggered_at = models.DateTimeField(auto_now_add=True)
    results      = models.JSONField(default=dict)
    success      = models.BooleanField(default=True)

    class Meta:
        ordering = ['-triggered_at']

    def __str__(self):
        status = 'OK' if self.success else 'FAILED'
        return f'Webhook run {self.triggered_at:%Y-%m-%d %H:%M} — {status}'


class SiteSettings(models.Model):
    """Singleton — agency contact info and medical director details used across all PDFs."""

    medical_director_name  = models.CharField(max_length=200, default='Dr. Sheila Webb-Bowles')
    medical_director_phone = models.CharField(max_length=30, default='308.630.3711')
    medical_director_title = models.CharField(max_length=200, default='Medical Director, PEMSE')

    agency_name          = models.CharField(max_length=200, default='Panhandle EMS Education, LLC')
    agency_address       = models.CharField(max_length=300, default='709 Rosedale Dr., Scottsbluff, NE 69361')
    agency_phone         = models.CharField(max_length=30, default='308.631.2424')
    agency_email         = models.CharField(max_length=200, default='emseducation19@gmail.com')
    agency_director      = models.CharField(max_length=200, default='Robin Darnall')
    agency_director_title = models.CharField(max_length=200, default='Program Director')
    asst_director        = models.CharField(max_length=200, blank=True)
    asst_director_title  = models.CharField(max_length=200, blank=True)

    ne_approval_number = models.CharField(max_length=100, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return 'Site Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        from django.conf import settings
        if settings.DEMO_MODE:
            # Never persist demo branding to the DB — always reflect whatever
            # AGENCY_* env vars are currently set, with no agency-specific
            # defaults bleeding into demo PDFs.
            return cls(
                medical_director_name=settings.AGENCY_DIRECTOR,
                medical_director_phone=settings.AGENCY_PHONE,
                medical_director_title='Program Administrator',
                agency_name=settings.AGENCY_NAME,
                agency_address=settings.AGENCY_ADDRESS,
                agency_phone=settings.AGENCY_PHONE,
                agency_email=settings.AGENCY_EMAIL,
                agency_director=settings.AGENCY_DIRECTOR,
                agency_director_title='Program Administrator',
            )
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
