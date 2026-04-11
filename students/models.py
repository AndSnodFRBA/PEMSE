from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class Student(AbstractUser):
    """Custom user model — one row = one enrolled student or staff member."""

    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        STAFF   = 'staff',   'Office Staff'

    role = models.CharField(
        max_length=10, choices=Role.choices, default=Role.STUDENT,
    )

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

    # ── Signatures (stores base64 PNG data from canvas pad) ───────────────────
    contract_signed     = models.BooleanField(default=False)
    contract_sig_name   = models.TextField(blank=True)
    contract_signed_at  = models.DateTimeField(null=True, blank=True)

    handbook_signed     = models.BooleanField(default=False)
    handbook_sig_name   = models.TextField(blank=True)
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
    def is_office_staff(self):
        return self.role == self.Role.STAFF or self.is_superuser or self.is_staff

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['student', 'course']]

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
