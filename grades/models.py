from django.db import models
from django.conf import settings
from django.utils import timezone


class GradeBook(models.Model):
    """One gradebook per student per course — the master record."""
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gradebooks'
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='gradebooks'
    )
    # Participation score — starts at 100, staff deduct points
    participation_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=100,
        help_text='Starts at 100. Staff deduct points per handbook policy.'
    )

    # FISDAP
    fisdap_attempt_1 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fisdap_attempt_2 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fisdap_passed = models.BooleanField(default=False)

    # Finalization / lock
    is_finalized    = models.BooleanField(default=False)
    finalized_at    = models.DateTimeField(null=True, blank=True)
    finalized_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='gradebooks_finalized'
    )
    finalized_notes = models.TextField(blank=True)

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['student', 'course']]
        ordering = ['course', 'student__last_name']

    def __str__(self):
        return f'{self.student.get_full_name()} — {self.course.name}'

    @property
    def fisdap_best_score(self):
        scores = [s for s in [self.fisdap_attempt_1, self.fisdap_attempt_2] if s is not None]
        return max(scores) if scores else None

    @property
    def quiz_average(self):
        quizzes = self.quiz_grades.all()
        if not quizzes:
            return None
        return round(sum(q.score for q in quizzes) / len(quizzes), 2)

    @property
    def skills_average(self):
        skills = self.skills_grades.all()
        if not skills:
            return None
        return round(sum(s.score for s in skills) / len(skills), 2)

    @property
    def component_1_average(self):
        """Quizzes + Worksheets + Participation + Skills — all equal weight — 30% of final"""
        components = []
        if self.quiz_average is not None:
            components.append(float(self.quiz_average))
        if self.skills_average is not None:
            components.append(float(self.skills_average))
        components.append(float(self.participation_score))
        worksheet_avg = self.worksheet_average
        if worksheet_avg is not None:
            components.append(float(worksheet_avg))
        if not components:
            return None
        return round(sum(components) / len(components), 2)

    @property
    def worksheet_average(self):
        worksheets = self.worksheet_grades.all()
        if not worksheets:
            return None
        return round(sum(w.score for w in worksheets) / len(worksheets), 2)

    @property
    def section_exam_average(self):
        """All section exams equal weight — 40% of final"""
        exams = self.section_exam_grades.filter(is_final_exam=False)
        if not exams:
            return None
        return round(sum(e.score for e in exams) / len(exams), 2)

    @property
    def final_exam_score(self):
        final = self.section_exam_grades.filter(is_final_exam=True).first()
        return float(final.score) if final else None

    @property
    def overall_grade(self):
        """Weighted average: Component1*0.30 + SectionExams*0.40 + FinalExam*0.30"""
        c1 = self.component_1_average
        se = self.section_exam_average
        fe = self.final_exam_score
        # Need all three components to calculate overall
        if c1 is None or se is None or fe is None:
            return None
        return round(float(c1) * 0.30 + float(se) * 0.40 + float(fe) * 0.30, 2)

    @property
    def letter_grade(self):
        g = self.overall_grade
        if g is None:
            return '—'
        if g >= 91:
            return 'A'
        if g >= 83:
            return 'B'
        if g >= 75:
            return 'C'
        if g >= 60:
            return 'D'
        return 'F'

    @property
    def is_passing(self):
        g = self.overall_grade
        return g is not None and g >= 75

    @property
    def section_exams_all_passing(self):
        """Per handbook: student must achieve 75% minimum on ALL section exams individually"""
        exams = self.section_exam_grades.filter(is_final_exam=False)
        if not exams:
            return None
        return all(e.score >= 75 for e in exams)

    @property
    def meets_completion_requirements(self):
        return (
            self.is_passing and
            self.section_exams_all_passing and
            self.fisdap_passed and
            (self.final_exam_score is not None and self.final_exam_score >= 75)
        )


class QuizGrade(models.Model):
    """Individual quiz score — per handbook: 2 attempts, max 5 resets, missed excused = max 75%, missed unexcused = 0"""
    gradebook = models.ForeignKey(GradeBook, on_delete=models.CASCADE, related_name='quiz_grades')
    quiz_name = models.CharField(max_length=200)
    quiz_number = models.PositiveIntegerField(help_text='e.g. 1, 2, 3 matching the course schedule')
    score = models.DecimalField(max_digits=5, decimal_places=2)
    attempt_number = models.PositiveIntegerField(default=1)
    was_reset = models.BooleanField(default=False)
    missed_excused = models.BooleanField(default=False, help_text='Max score 75% per handbook')
    missed_unexcused = models.BooleanField(default=False, help_text='Score = 0 per handbook')
    date_taken = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='quiz_grades_entered'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['quiz_number', 'attempt_number']
        unique_together = [['gradebook', 'quiz_number']]

    def __str__(self):
        return f'{self.gradebook.student.get_full_name()} — Quiz {self.quiz_number}: {self.score}%'


class SectionExamGrade(models.Model):
    """Section exam score — per handbook: max 2 resets, reset max score 75%, final exam min 75% to pass"""
    gradebook = models.ForeignKey(GradeBook, on_delete=models.CASCADE, related_name='section_exam_grades')
    exam_name = models.CharField(max_length=200)
    exam_number = models.PositiveIntegerField(null=True, blank=True)
    is_final_exam = models.BooleanField(default=False, help_text='Mark True for the Final Written Exam')
    score = models.DecimalField(max_digits=5, decimal_places=2)
    was_reset = models.BooleanField(default=False)
    reset_count = models.PositiveIntegerField(default=0, help_text='Max 2 resets per handbook')
    date_taken = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='exam_grades_entered'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['is_final_exam', 'exam_number']

    def __str__(self):
        label = 'Final Exam' if self.is_final_exam else f'Section Exam {self.exam_number}'
        return f'{self.gradebook.student.get_full_name()} — {label}: {self.score}%'

    @property
    def is_passing(self):
        return self.score >= 75


class WorksheetGrade(models.Model):
    """Worksheet/homework assignment score"""
    gradebook = models.ForeignKey(GradeBook, on_delete=models.CASCADE, related_name='worksheet_grades')
    assignment_name = models.CharField(max_length=200)
    score = models.DecimalField(max_digits=5, decimal_places=2)
    date_submitted = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='worksheet_grades_entered'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['assignment_name']

    def __str__(self):
        return f'{self.gradebook.student.get_full_name()} — {self.assignment_name}: {self.score}%'


class SkillsGrade(models.Model):
    """Skills lab evaluation score"""
    gradebook = models.ForeignKey(GradeBook, on_delete=models.CASCADE, related_name='skills_grades')
    skill_name = models.CharField(max_length=200)
    score = models.DecimalField(max_digits=5, decimal_places=2)
    passed = models.BooleanField(default=False)
    attempt_number = models.PositiveIntegerField(default=1)
    date_evaluated = models.DateField(null=True, blank=True)
    evaluator_name = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='skills_grades_entered'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['skill_name', 'attempt_number']

    def __str__(self):
        return f'{self.gradebook.student.get_full_name()} — {self.skill_name}: {self.score}%'


class ParticipationDeduction(models.Model):
    """Records each participation point deduction per handbook policy"""

    class Reason(models.TextChoices):
        EXCUSED_ABSENCE    = 'excused_absence',    'Excused absence (-10 points)'
        UNEXCUSED_ABSENCE  = 'unexcused_absence',  'Unexcused absence (-25 points)'
        SLEEPING           = 'sleeping',            'Sleeping in class (-25 points)'
        DISRUPTIVE         = 'disruptive',          'Argumentative/Disruptive (-25 points)'
        CHEATING           = 'cheating',            'Cheating (-50 points)'
        OTHER              = 'other',               'Other (custom amount)'

    DEDUCTION_AMOUNTS = {
        'excused_absence':   10,
        'unexcused_absence': 25,
        'sleeping':          25,
        'disruptive':        25,
        'cheating':          50,
    }

    gradebook   = models.ForeignKey(GradeBook, on_delete=models.CASCADE, related_name='participation_deductions')
    reason      = models.CharField(max_length=30, choices=Reason.choices)
    points      = models.PositiveIntegerField(help_text='Points deducted')
    date        = models.DateField(default=timezone.now)
    notes       = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='participation_deductions_recorded'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.gradebook.student.get_full_name()} — {self.get_reason_display()} ({self.date})'

    def save(self, *args, **kwargs):
        # Auto-set points from reason if not custom
        if self.reason != self.Reason.OTHER and not self.points:
            self.points = self.DEDUCTION_AMOUNTS.get(self.reason, 0)
        super().save(*args, **kwargs)
        self._recalc_participation_score()

    def delete(self, *args, **kwargs):
        gb = self.gradebook
        super().delete(*args, **kwargs)
        self._recalc_participation_score(gb)

    def _recalc_participation_score(self, gradebook=None):
        # Deleting a deduction must also restore the score it took away —
        # recomputing from scratch each time keeps this correct either way.
        gb = gradebook or self.gradebook
        total_deductions = sum(d.points for d in gb.participation_deductions.all())
        gb.participation_score = max(0, 100 - total_deductions)
        gb.save(update_fields=['participation_score', 'updated_at'])


class GradeChangeLog(models.Model):
    """Audit trail — every create/update/delete on a grade record."""

    class ChangeType(models.TextChoices):
        CREATE = 'create', 'Created'
        UPDATE = 'update', 'Updated'
        DELETE = 'delete', 'Deleted'

    gradebook    = models.ForeignKey(GradeBook, on_delete=models.CASCADE, related_name='change_logs')
    changed_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='grade_changes_made'
    )
    change_type  = models.CharField(max_length=10, choices=ChangeType.choices)
    model_name   = models.CharField(max_length=50, help_text='Which model was changed e.g. QuizGrade')
    record_id    = models.PositiveIntegerField(null=True, blank=True)
    field_name   = models.CharField(max_length=100, blank=True)
    old_value    = models.TextField(blank=True)
    new_value    = models.TextField(blank=True)
    notes        = models.TextField(blank=True)
    changed_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f'{self.model_name} {self.change_type} by {self.changed_by} at {self.changed_at:%Y-%m-%d %H:%M}'
