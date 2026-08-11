from django.db import models
from django.conf import settings
from django.utils import timezone


class InstructorCourseAssignment(models.Model):
    """Links an instructor to a course they are teaching."""

    ROLE_CHOICES = [
        ('primary',   'Primary Instructor'),
        ('assistant', 'Assistant Instructor'),
        ('skills',    'Skills Evaluator'),
        ('clinical',  'Clinical Supervisor'),
        ('guest',     'Guest / Subject Matter Expert'),
    ]

    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_assignments',
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='instructor_assignments',
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, on_delete=models.SET_NULL,
        related_name='assignments_made',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        unique_together = [['instructor', 'course', 'role']]
        ordering = ['course', 'role']

    def __str__(self):
        return f'{self.instructor.get_full_name()} — {self.course} ({self.get_role_display()})'


class InstructionalHourLog(models.Model):
    """Instructor logs their teaching hours per 172 NAC Chapter 13."""

    SESSION_TYPES = [
        ('lecture',     'Lecture / Didactic'),
        ('lab',         'Skills Lab'),
        ('simulation',  'Simulation'),
        ('clinical',    'Clinical Supervision'),
        ('field',       'Field Experience Supervision'),
        ('testing',     'Exam / Testing'),
        ('remediation', 'Remediation'),
        ('meeting',     'Instructor Meeting'),
        ('preparation', 'Course Preparation'),
        ('other',       'Other'),
    ]

    instructor   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hour_logs',
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='hour_logs',
    )
    session_date     = models.DateField()
    start_time       = models.TimeField()
    end_time         = models.TimeField()
    hours            = models.DecimalField(max_digits=4, decimal_places=2)
    session_type     = models.CharField(max_length=30, choices=SESSION_TYPES)
    topic_covered    = models.CharField(max_length=300)
    students_present = models.PositiveIntegerField(default=0)
    location         = models.CharField(max_length=200, blank=True)
    notes            = models.TextField(blank=True)

    # Verification
    verified    = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='hours_verified',
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-session_date', '-start_time']

    def __str__(self):
        return f'{self.instructor.get_full_name()} — {self.session_date} — {self.hours}hrs'


class AttendanceRecord(models.Model):
    """Instructor takes attendance for each class session."""

    SESSION_TYPES = [
        ('lecture',    'Lecture / Didactic'),
        ('lab',        'Skills Lab'),
        ('simulation', 'Simulation'),
        ('clinical',   'Clinical'),
        ('field',      'Field Experience'),
        ('testing',    'Exam / Testing'),
        ('other',      'Other'),
    ]

    course        = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='attendance_records',
    )
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_taken',
    )
    calendar_event = models.ForeignKey(
        'schedule.CalendarEvent',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='attendance_records',
    )
    session_date  = models.DateField()
    session_type  = models.CharField(max_length=30, choices=SESSION_TYPES)
    session_topic = models.CharField(max_length=300, blank=True)
    session_start = models.TimeField(null=True, blank=True)
    session_end   = models.TimeField(null=True, blank=True)
    notes         = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-session_date']
        # NOTE: session_type is intentionally included in this constraint.
        # This allows a course to have both a lecture AND a skills lab
        # recorded on the same date (they differ by session_type).
        # Do NOT simplify to (course, session_date) — that would break
        # combined lecture+skills Monday sessions.
        unique_together = [['course', 'session_date', 'session_type']]

    def __str__(self):
        return f'{self.course} — {self.session_date} — {self.get_session_type_display()}'

    @property
    def is_editable(self):
        from datetime import timedelta
        return timezone.now() < self.created_at + timedelta(hours=48)


class StudentAttendance(models.Model):
    """Individual student attendance for each session."""

    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        ABSENT  = 'absent',  'Absent'
        LATE    = 'late',    'Late (arrived after start)'
        EXCUSED = 'excused', 'Excused absence'
        MAKEUP  = 'makeup',  'Make-up session'

    session = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.CASCADE,
        related_name='student_attendance',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_entries',
    )
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT)
    arrival_time = models.TimeField(null=True, blank=True, help_text='Actual arrival time if late')
    notes        = models.TextField(blank=True)

    class Meta:
        unique_together = [['session', 'student']]

    def __str__(self):
        return f'{self.student.get_full_name()} — {self.session} — {self.get_status_display()}'


class InstructorObservation(models.Model):
    """Per 172 NAC 13-004(F)(i) — written policies for periodic observation of instructors."""

    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='observations',
    )
    course = models.ForeignKey(
        'courses.Course',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='instructor_observations',
    )
    observed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='observations_conducted',
    )
    observation_date = models.DateField()
    session_observed = models.CharField(max_length=200)

    RATING_CHOICES = [(i, i) for i in range(1, 6)]

    preparation        = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    content_knowledge  = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    delivery           = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    student_engagement = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    time_management    = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    professionalism    = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)

    strengths      = models.TextField(blank=True)
    opportunities  = models.TextField(blank=True)
    action_items   = models.TextField(blank=True)
    overall_rating = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)

    instructor_acknowledged    = models.BooleanField(default=False)
    instructor_acknowledged_at = models.DateTimeField(null=True, blank=True)
    instructor_response        = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-observation_date']

    def __str__(self):
        return f'Observation — {self.instructor.get_full_name()} — {self.observation_date}'

    @property
    def average_rating(self):
        fields = [self.preparation, self.content_knowledge, self.delivery,
                  self.student_engagement, self.time_management, self.professionalism]
        vals = [f for f in fields if f is not None]
        return round(sum(vals) / len(vals), 1) if vals else None


class InstructorMeeting(models.Model):
    """Per 172 NAC 13-004(F)(iv) — semi-annual meetings with each instructor."""

    MEETING_TYPES = [
        ('semi_annual', 'Semi-Annual Review'),
        ('remediation', 'Remediation Meeting'),
        ('other',       'Other'),
    ]

    instructor   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='instructor_meetings',
    )
    conducted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='meetings_conducted',
    )
    meeting_date      = models.DateField()
    meeting_type      = models.CharField(max_length=20, choices=MEETING_TYPES)
    topics_discussed  = models.TextField()
    action_items      = models.TextField(blank=True)
    next_meeting_date = models.DateField(null=True, blank=True)

    instructor_acknowledged    = models.BooleanField(default=False)
    instructor_acknowledged_at = models.DateTimeField(null=True, blank=True)
    instructor_signature       = models.TextField(blank=True, help_text='Base64 canvas signature')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-meeting_date']

    def __str__(self):
        return f'{self.get_meeting_type_display()} — {self.instructor.get_full_name()} — {self.meeting_date}'


class RemediationPlan(models.Model):
    """Per 172 NAC 13-004(F)(iii) — remediation plans kept 5 years."""

    class Status(models.TextChoices):
        ACTIVE    = 'active',    'Active'
        COMPLETED = 'completed', 'Completed'
        EXTENDED  = 'extended',  'Extended'

    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='remediation_plans',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='remediation_plans_created',
    )
    issue_identified = models.TextField()
    plan_details     = models.TextField()
    target_date      = models.DateField()
    created_date     = models.DateField(auto_now_add=True)

    status           = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    completion_date  = models.DateField(null=True, blank=True)
    completion_notes = models.TextField(blank=True)

    instructor_acknowledged = models.BooleanField(default=False)
    instructor_signature    = models.TextField(blank=True, help_text='Base64 canvas signature')

    # Must be kept 5 years per 172 NAC Chapter 13
    retain_until = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-created_date']

    def save(self, *args, **kwargs):
        if not self.retain_until:
            # created_date is auto_now_add, so on first save it isn't populated
            # until inside super().save() — use today's date for new instances.
            base_date = self.created_date if self.pk else timezone.now().date()
            try:
                self.retain_until = base_date.replace(year=base_date.year + 5)
            except ValueError:
                self.retain_until = base_date.replace(month=2, day=28, year=base_date.year + 5)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Remediation — {self.instructor.get_full_name()} — {self.created_date}'


class InstructorNote(models.Model):
    """Instructor notes about a student — visible to staff only."""
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='instructor_notes_written',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='instructor_notes_received',
    )
    course = models.ForeignKey(
        'courses.Course',
        null=True, blank=True,
        on_delete=models.SET_NULL,
    )
    note       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Note by {self.instructor.get_full_name()} re {self.student.get_full_name()}'
