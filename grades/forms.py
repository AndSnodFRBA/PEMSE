from django import forms
from .models import QuizGrade, SectionExamGrade, WorksheetGrade, SkillsGrade, ParticipationDeduction, GradeBook


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            if isinstance(field.widget, (forms.CheckboxInput,)):
                field.widget.attrs['class'] = (existing + ' form-check-input').strip()
            else:
                field.widget.attrs['class'] = (existing + ' form-control').strip()


class QuizGradeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = QuizGrade
        fields = [
            'quiz_name', 'score', 'attempt_number', 'was_reset',
            'missed_excused', 'missed_unexcused', 'date_taken', 'notes',
        ]
        widgets = {
            'date_taken': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def clean(self):
        cleaned = super().clean()
        missed_excused = cleaned.get('missed_excused')
        missed_unexcused = cleaned.get('missed_unexcused')
        score = cleaned.get('score')

        if missed_excused and missed_unexcused:
            raise forms.ValidationError('A quiz cannot be both an excused and unexcused miss.')

        # Per handbook: missed excused caps the score at 75%, missed unexcused forces 0.
        if missed_unexcused:
            cleaned['score'] = 0
        elif missed_excused and score is not None and score > 75:
            cleaned['score'] = 75
        return cleaned


class SectionExamGradeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SectionExamGrade
        fields = [
            'exam_name', 'exam_number', 'is_final_exam', 'score',
            'was_reset', 'reset_count', 'date_taken', 'notes',
        ]
        widgets = {
            'date_taken': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def clean(self):
        cleaned = super().clean()
        was_reset = cleaned.get('was_reset')
        score = cleaned.get('score')
        # Per handbook: a reset exam's retake score is capped at 75%.
        if was_reset and score is not None and score > 75:
            cleaned['score'] = 75
        return cleaned


class WorksheetGradeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WorksheetGrade
        fields = ['assignment_name', 'score', 'date_submitted', 'notes']
        widgets = {
            'date_submitted': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class SkillsGradeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SkillsGrade
        fields = ['skill_name', 'score', 'passed', 'attempt_number', 'date_evaluated', 'evaluator_name', 'notes']
        widgets = {
            'date_evaluated': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class ParticipationDeductionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ParticipationDeduction
        fields = ['reason', 'points', 'date', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['points'].required = False
        self.fields['points'].help_text = 'Auto-filled from reason unless "Other" is selected.'

    def clean(self):
        cleaned = super().clean()
        reason = cleaned.get('reason')
        points = cleaned.get('points')
        if reason and reason != ParticipationDeduction.Reason.OTHER:
            cleaned['points'] = ParticipationDeduction.DEDUCTION_AMOUNTS.get(reason, 0)
        elif reason == ParticipationDeduction.Reason.OTHER and not points:
            raise forms.ValidationError('Enter a custom point value for "Other".')
        return cleaned


class FisdapForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = GradeBook
        fields = ['fisdap_attempt_1', 'fisdap_attempt_2', 'fisdap_passed']
