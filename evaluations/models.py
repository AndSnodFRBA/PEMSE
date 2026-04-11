import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ClinicalRotation(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rotations'
    )
    site_name    = models.CharField(max_length=200)
    site_address = models.CharField(max_length=300, blank=True)
    site_city    = models.CharField(max_length=100, blank=True)
    site_type    = models.CharField(max_length=50, choices=[
        ('ems_field', 'EMS Field'),
        ('er',        'Emergency Department'),
        ('icu',       'ICU'),
        ('fire',      'Fire Department'),
        ('other',     'Other'),
    ])
    rotation_date    = models.DateField()
    shift_start      = models.TimeField(null=True, blank=True)
    shift_end        = models.TimeField(null=True, blank=True)
    hours_completed  = models.DecimalField(max_digits=4, decimal_places=1)
    patient_contacts = models.PositiveIntegerField(default=0)
    course           = models.ForeignKey(
        'courses.Course', null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-rotation_date']

    def __str__(self):
        return f"{self.student.get_full_name()} — {self.site_name} ({self.rotation_date})"


RATING_CHOICES = [(i, i) for i in range(1, 6)]


class PreceptorEvaluation(models.Model):
    rotation = models.OneToOneField(
        ClinicalRotation, on_delete=models.CASCADE, related_name='preceptor_eval'
    )

    # Preceptor contact info — filled in by student when requesting
    preceptor_name  = models.CharField(max_length=200)
    preceptor_email = models.EmailField()
    preceptor_title = models.CharField(max_length=100, blank=True)

    # Token for the preceptor link
    token         = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    token_expires = models.DateTimeField()

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending — awaiting preceptor'
        COMPLETED = 'completed', 'Completed'
        EXPIRED   = 'expired',   'Expired'

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    link_sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    preceptor_ip = models.GenericIPAddressField(null=True, blank=True)

    # ── Professional Behavior (1–5) ────────────────────────────────────────────
    appearance_professional = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    punctuality             = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    communication_patients  = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    communication_team      = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    attitude_motivation     = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)

    # ── Clinical Skills (1–5) ──────────────────────────────────────────────────
    patient_assessment          = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    clinical_skills_performance = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    critical_thinking           = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    medical_knowledge           = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    documentation               = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)

    # ── Overall ───────────────────────────────────────────────────────────────
    overall_performance = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    recommended_to_pass = models.BooleanField(null=True, blank=True)

    strengths             = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    additional_comments   = models.TextField(blank=True)

    # Rating scale:
    # 1=Unsatisfactory  2=Below Expectations  3=Meets Expectations
    # 4=Exceeds Expectations  5=Outstanding

    class Meta:
        verbose_name = 'Preceptor evaluation'

    def __str__(self):
        return f"Preceptor eval — {self.rotation}"

    @property
    def is_expired_now(self):
        return self.status == self.Status.PENDING and timezone.now() > self.token_expires

    def average_score(self):
        fields = [
            self.appearance_professional, self.punctuality,
            self.communication_patients, self.communication_team,
            self.attitude_motivation, self.patient_assessment,
            self.clinical_skills_performance, self.critical_thinking,
            self.medical_knowledge, self.documentation,
            self.overall_performance,
        ]
        scored = [f for f in fields if f is not None]
        return round(sum(scored) / len(scored), 1) if scored else None


class CourseEvaluation(models.Model):
    """Mid-course or end-of-course evaluation filled out by the student."""

    class EvalType(models.TextChoices):
        MID_COURSE = 'mid', 'Mid-Course Evaluation'
        END_COURSE = 'end', 'End-of-Course Evaluation'

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending — awaiting student'
        COMPLETED = 'completed', 'Completed'
        EXPIRED   = 'expired',   'Expired'

    student    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_evaluations'
    )
    course     = models.ForeignKey(
        'courses.Course', on_delete=models.CASCADE, related_name='evaluations'
    )
    eval_type  = models.CharField(max_length=10, choices=EvalType.choices)
    status     = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    token      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='evals_created'
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # ── Section 1: Course Content & Curriculum ────────────────────────────────
    # 1=Strongly Disagree  2=Disagree  3=Neutral  4=Agree  5=Strongly Agree
    content_objectives_clear       = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    content_material_relevant      = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    content_material_current       = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    content_difficulty_appropriate = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    content_theory_lab_balance     = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])

    # ── Section 2: Instruction Quality ───────────────────────────────────────
    instruction_knowledge          = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    instruction_communication      = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    instruction_feedback           = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    instruction_availability       = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    instruction_preparation        = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    instruction_respected_students = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])

    # ── Section 3: Facilities & Resources ────────────────────────────────────
    facility_classroom_adequate  = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    facility_equipment_adequate  = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    facility_supplies_adequate   = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    facility_schedule_reasonable = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])

    # ── Section 4: Online / Hybrid ────────────────────────────────────────────
    online_platform_easy_to_use = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    online_content_organized    = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    online_support_available    = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])

    # ── Section 5: Overall ────────────────────────────────────────────────────
    overall_satisfaction        = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    overall_recommend_to_others = models.BooleanField(null=True, blank=True)
    overall_prepared_for_nremt  = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])

    # ── End-of-Course only ────────────────────────────────────────────────────
    eoc_registration_process     = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    eoc_staff_helpfulness        = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    eoc_value_for_money          = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    eoc_would_take_future_course = models.BooleanField(null=True, blank=True)
    eoc_how_did_you_hear         = models.CharField(max_length=50, blank=True, choices=[
        ('word_of_mouth', 'Word of mouth'),
        ('social_media',  'Social media'),
        ('department',    'My fire/EMS department'),
        ('internet',      'Internet search'),
        ('returning',     'Returning student'),
        ('other',         'Other'),
    ])

    # ── Written feedback (both types) ─────────────────────────────────────────
    what_worked_well        = models.TextField(blank=True)
    what_could_be_improved  = models.TextField(blank=True)
    suggestions_for_future  = models.TextField(blank=True)
    additional_comments     = models.TextField(blank=True)

    # ── Mid-Course only ───────────────────────────────────────────────────────
    mid_keeping_up_with_material = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    mid_support_needed           = models.TextField(blank=True)
    mid_concerns                 = models.TextField(blank=True)

    class Meta:
        ordering       = ['-created_at']
        unique_together = [['student', 'course', 'eval_type']]

    def __str__(self):
        return f'{self.student} — {self.get_eval_type_display()} — {self.course}'

    @property
    def average_score(self):
        fields = [
            self.content_objectives_clear, self.content_material_relevant,
            self.content_material_current, self.content_difficulty_appropriate,
            self.content_theory_lab_balance, self.instruction_knowledge,
            self.instruction_communication, self.instruction_feedback,
            self.instruction_availability, self.instruction_preparation,
            self.instruction_respected_students, self.facility_classroom_adequate,
            self.facility_equipment_adequate, self.facility_supplies_adequate,
            self.facility_schedule_reasonable, self.overall_satisfaction,
        ]
        scores = [f for f in fields if f is not None]
        return round(sum(scores) / len(scores), 1) if scores else None


class StudentSiteEvaluation(models.Model):
    rotation     = models.OneToOneField(
        ClinicalRotation, on_delete=models.CASCADE, related_name='student_eval'
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    # Site evaluation (1–5)
    site_organization           = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    site_learning_opportunities = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    site_equipment_available    = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    site_patient_volume         = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    site_staff_welcoming        = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    site_would_return           = models.BooleanField(null=True, blank=True)

    # Preceptor evaluation (1–5)
    preceptor_knowledge        = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    preceptor_teaching_style   = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    preceptor_feedback_quality = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    preceptor_professionalism  = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    preceptor_overall          = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)

    best_part_of_rotation  = models.TextField(blank=True)
    what_could_be_improved = models.TextField(blank=True)
    would_you_recommend    = models.BooleanField(null=True, blank=True)
    additional_comments    = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Student site evaluation'

    def __str__(self):
        return f"Site eval — {self.rotation}"
