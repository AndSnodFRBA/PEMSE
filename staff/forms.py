from django import forms

from courses.models import Course, CourseEnrollment
from documents.models import StudentDocument
from students.models import (
    Announcement, CognitiveExamRecord, CourseCompletionRecord,
    CourseReportRecord, EntranceRequirementRecord,
    PatientContactRecord, PaymentHistory, PsychomotorSkillRecord, Student,
    StudentNote,
)
from instructor.models import (
    InstructorCourseAssignment, InstructorObservation,
    InstructorMeeting, RemediationPlan,
)


class InvitationForm(forms.Form):
    email = forms.EmailField(
        label='Student email address',
        widget=forms.EmailInput(attrs={'placeholder': 'student@email.com', 'class': 'form-control'}),
    )
    course = forms.ModelChoiceField(
        queryset=Course.objects.filter(is_active=True).order_by('option_number'),
        label='Course to assign',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if Student.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class DocumentReviewForm(forms.Form):
    STATUS_CHOICES = [
        ('approved', 'Approve'),
        ('rejected', 'Reject'),
    ]
    status = forms.ChoiceField(choices=STATUS_CHOICES, widget=forms.RadioSelect)
    notes  = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Optional note to student…'}),
    )


class StaffAnnouncementForm(forms.ModelForm):
    class Meta:
        model   = Announcement
        fields  = ['title', 'body', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'body':  forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class StaffStudentEditForm(forms.ModelForm):
    class Meta:
        model  = Student
        fields = [
            'first_name', 'last_name', 'email', 'phone', 'ok_to_text',
            'address', 'city', 'state', 'zip_code', 'date_of_birth',
            'enroll_status', 'shirt_size',
        ]
        widgets = {
            'first_name':    forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':     forms.TextInput(attrs={'class': 'form-control'}),
            'email':         forms.EmailInput(attrs={'class': 'form-control'}),
            'phone':         forms.TextInput(attrs={'class': 'form-control'}),
            'ok_to_text':    forms.Select(choices=[(True, 'Yes'), (False, 'No'), ('', '—')], attrs={'class': 'form-select'}),
            'address':       forms.TextInput(attrs={'class': 'form-control'}),
            'city':          forms.TextInput(attrs={'class': 'form-control'}),
            'state':         forms.TextInput(attrs={'class': 'form-control', 'maxlength': '2'}),
            'zip_code':      forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'enroll_status': forms.Select(attrs={'class': 'form-select'}),
            'shirt_size':    forms.TextInput(attrs={'class': 'form-control'}),
        }


class CourseForm(forms.ModelForm):
    class Meta:
        model  = Course
        fields = [
            'option_number', 'tag', 'name', 'description', 'licensure',
            'price', 'book_price', 'min_down', 'includes_shirt', 'is_active',
            'location_name', 'location_address', 'location_city', 'location_state',
            'start_date', 'end_date', 'registration_close_date',
            'max_students', 'schedule_notes',
        ]
        widgets = {
            'option_number':          forms.NumberInput(attrs={'class': 'form-control'}),
            'tag':                    forms.TextInput(attrs={'class': 'form-control'}),
            'name':                   forms.TextInput(attrs={'class': 'form-control'}),
            'description':            forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'licensure':              forms.Select(attrs={'class': 'form-select'}),
            'price':                  forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'book_price':             forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_down':               forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'location_name':          forms.TextInput(attrs={'class': 'form-control'}),
            'location_address':       forms.TextInput(attrs={'class': 'form-control'}),
            'location_city':          forms.TextInput(attrs={'class': 'form-control'}),
            'location_state':         forms.TextInput(attrs={'class': 'form-control', 'maxlength': '2'}),
            'start_date':             forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date':               forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'registration_close_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'max_students':           forms.NumberInput(attrs={'class': 'form-control'}),
            'schedule_notes':         forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class StaffAssignCourseForm(forms.ModelForm):
    class Meta:
        model  = CourseEnrollment
        fields = ['course']
        widgets = {'course': forms.Select(attrs={'class': 'form-select form-select-sm'})}


class ReminderBulkSendForm(forms.Form):
    AUDIENCE_CHOICES = [
        ('all_active',              'All active students'),
        ('registration_incomplete', 'Registration incomplete'),
        ('balance_due',             'Balance due'),
    ]
    course = forms.ModelChoiceField(
        queryset=Course.objects.order_by('option_number'),
        required=False, empty_label='All courses',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    audience = forms.ChoiceField(choices=AUDIENCE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    subject  = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    body     = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6}))


class PaymentHistoryForm(forms.ModelForm):
    class Meta:
        model  = PaymentHistory
        fields = ['amount', 'payment_date', 'method', 'check_number', 'notes']
        widgets = {
            'amount':       forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'method':       forms.Select(attrs={'class': 'form-select'}),
            'check_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Check #'}),
            'notes':        forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes…'}),
        }


# ── 172 NAC Compliance Forms ──────────────────────────────────────────────────

_fc = {'class': 'form-control'}
_fs = {'class': 'form-select'}
_date = {'class': 'form-control', 'type': 'date'}


class CognitiveExamForm(forms.ModelForm):
    class Meta:
        model  = CognitiveExamRecord
        fields = ['exam_name', 'exam_date', 'score', 'passed', 'attempt_number', 'notes']
        widgets = {
            'exam_name':      forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. Unit 1 Written Exam'}),
            'exam_date':      forms.DateInput(attrs=_date),
            'score':          forms.NumberInput(attrs={**_fc, 'step': '0.01', 'min': '0', 'max': '100'}),
            'passed':         forms.Select(choices=[(True, 'Pass'), (False, 'Fail')], attrs=_fs),
            'attempt_number': forms.NumberInput(attrs={**_fc, 'min': '1'}),
            'notes':          forms.Textarea(attrs={**_fc, 'rows': 2}),
        }


class StudentNoteForm(forms.ModelForm):
    class Meta:
        model  = StudentNote
        fields = ['note_type', 'body']
        widgets = {
            'note_type': forms.Select(attrs=_fs),
            'body':      forms.Textarea(attrs={**_fc, 'rows': 3, 'placeholder': 'Note details…'}),
        }


class PsychomotorSkillForm(forms.ModelForm):
    class Meta:
        model  = PsychomotorSkillRecord
        fields = ['skill_name', 'evaluation_date', 'passed', 'attempt_number',
                  'evaluator_name', 'evaluator_qualifications', 'notes']
        widgets = {
            'skill_name':               forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. BVM Ventilation'}),
            'evaluation_date':          forms.DateInput(attrs=_date),
            'passed':                   forms.Select(choices=[(True, 'Pass'), (False, 'Fail')], attrs=_fs),
            'attempt_number':           forms.NumberInput(attrs={**_fc, 'min': '1'}),
            'evaluator_name':           forms.TextInput(attrs=_fc),
            'evaluator_qualifications': forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. NREMT-P, RN'}),
            'notes':                    forms.Textarea(attrs={**_fc, 'rows': 2}),
        }


class PatientContactForm(forms.ModelForm):
    class Meta:
        model  = PatientContactRecord
        fields = [
            'contact_date', 'site_name', 'contact_type',
            'supervisor_name', 'supervisor_license_level',
            'patient_age_group', 'chief_complaint',
            'iv_start_attempted', 'iv_start_successful',
            'airway_placement_attempted', 'airway_placement_successful',
            'notes',
        ]
        widgets = {
            'contact_date':              forms.DateInput(attrs=_date),
            'site_name':                 forms.TextInput(attrs=_fc),
            'contact_type':              forms.Select(attrs=_fs),
            'supervisor_name':           forms.TextInput(attrs=_fc),
            'supervisor_license_level':  forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. NREMT-P'}),
            'patient_age_group':         forms.Select(attrs=_fs),
            'chief_complaint':           forms.TextInput(attrs=_fc),
            'notes':                     forms.Textarea(attrs={**_fc, 'rows': 2}),
        }


class EntranceRequirementForm(forms.ModelForm):
    class Meta:
        model  = EntranceRequirementRecord
        fields = ['verified', 'verified_date', 'document_on_file', 'notes']
        widgets = {
            'verified_date':    forms.DateInput(attrs=_date),
            'notes':            forms.TextInput(attrs={**_fc, 'placeholder': 'Optional note…'}),
        }


class CourseCompletionForm(forms.ModelForm):
    class Meta:
        model  = CourseCompletionRecord
        fields = [
            'completion_date', 'withdrew', 'withdrawal_date', 'withdrawal_reason',
            'total_hours', 'didactic_hours', 'clinical_hours', 'field_internship_hours',
            'verified_by_name', 'verified_by_title', 'verification_date',
            'certificate_issued', 'certificate_issued_date',
            'nremt_eligibility_sent', 'nremt_eligibility_date',
            'nremt_cognitive_result', 'nremt_cognitive_date', 'nremt_cognitive_attempts',
            'nremt_psychomotor_result', 'nremt_psychomotor_date',
        ]
        widgets = {
            'completion_date':          forms.DateInput(attrs=_date),
            'withdrawal_date':          forms.DateInput(attrs=_date),
            'withdrawal_reason':        forms.Textarea(attrs={**_fc, 'rows': 2}),
            'total_hours':              forms.NumberInput(attrs={**_fc, 'step': '0.5', 'min': '0'}),
            'didactic_hours':           forms.NumberInput(attrs={**_fc, 'step': '0.5', 'min': '0'}),
            'clinical_hours':           forms.NumberInput(attrs={**_fc, 'step': '0.5', 'min': '0'}),
            'field_internship_hours':   forms.NumberInput(attrs={**_fc, 'step': '0.5', 'min': '0'}),
            'verified_by_name':         forms.TextInput(attrs=_fc),
            'verified_by_title':        forms.TextInput(attrs=_fc),
            'verification_date':        forms.DateInput(attrs=_date),
            'certificate_issued_date':  forms.DateInput(attrs=_date),
            'nremt_eligibility_date':   forms.DateInput(attrs=_date),
            'nremt_cognitive_result':   forms.Select(attrs=_fs),
            'nremt_cognitive_date':     forms.DateInput(attrs=_date),
            'nremt_cognitive_attempts': forms.NumberInput(attrs={**_fc, 'min': '0'}),
            'nremt_psychomotor_result': forms.Select(attrs=_fs),
            'nremt_psychomotor_date':   forms.DateInput(attrs=_date),
        }


class CourseReportForm(forms.ModelForm):
    class Meta:
        model  = CourseReportRecord
        fields = [
            'training_agency_name', 'course_location', 'instructor_names',
            'students_enrolled', 'students_withdrew', 'students_completed',
            'total_didactic_hours', 'total_clinical_hours', 'total_field_hours',
            'report_submitted_to_department', 'report_submitted_date',
            'submission_deadline', 'notes',
        ]
        widgets = {
            'training_agency_name':  forms.TextInput(attrs=_fc),
            'course_location':       forms.TextInput(attrs=_fc),
            'instructor_names':      forms.Textarea(attrs={**_fc, 'rows': 2}),
            'students_enrolled':     forms.NumberInput(attrs={**_fc, 'min': '0'}),
            'students_withdrew':     forms.NumberInput(attrs={**_fc, 'min': '0'}),
            'students_completed':    forms.NumberInput(attrs={**_fc, 'min': '0'}),
            'total_didactic_hours':  forms.NumberInput(attrs={**_fc, 'step': '0.5', 'min': '0'}),
            'total_clinical_hours':  forms.NumberInput(attrs={**_fc, 'step': '0.5', 'min': '0'}),
            'total_field_hours':     forms.NumberInput(attrs={**_fc, 'step': '0.5', 'min': '0'}),
            'report_submitted_date': forms.DateInput(attrs=_date),
            'submission_deadline':   forms.DateInput(attrs=_date),
            'notes':                 forms.Textarea(attrs={**_fc, 'rows': 2}),
        }


# ── Instructor Management Forms ───────────────────────────────────────────────

class InstructorCreateForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={**_fc, 'placeholder': 'Min. 8 characters'}),
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={**_fc, 'placeholder': 'Repeat password'}),
    )

    class Meta:
        model  = Student
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'instructor_license_number', 'instructor_license_level',
            'instructor_license_expiry', 'instructor_employer',
        ]
        widgets = {
            'first_name':                  forms.TextInput(attrs=_fc),
            'last_name':                   forms.TextInput(attrs=_fc),
            'email':                       forms.EmailInput(attrs=_fc),
            'phone':                       forms.TextInput(attrs=_fc),
            'instructor_license_number':   forms.TextInput(attrs=_fc),
            'instructor_license_level':    forms.Select(attrs=_fs),
            'instructor_license_expiry':   forms.DateInput(attrs=_date),
            'instructor_employer':         forms.TextInput(attrs=_fc),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if Student.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email'].lower()
        user.email    = self.cleaned_data['email'].lower()
        user.role     = Student.Role.INSTRUCTOR
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class StaffInviteAcceptForm(forms.ModelForm):
    """Filled out by an invited staff member to set up their own account.

    Email is intentionally excluded — it's fixed to whatever address the
    invitation was sent to, so it can't be swapped out from the form.
    """
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Min. 8 characters'}),
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Repeat password'}),
    )

    class Meta:
        model  = Student
        fields = ['first_name', 'last_name', 'phone']

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned


class InstructorCourseAssignmentForm(forms.ModelForm):
    class Meta:
        model  = InstructorCourseAssignment
        fields = ['course', 'role', 'is_active']
        widgets = {
            'course': forms.Select(attrs=_fs),
            'role':   forms.Select(attrs=_fs),
        }

    def __init__(self, *args, instructor=None, **kwargs):
        self.instructor = instructor
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        course  = cleaned.get('course')
        role    = cleaned.get('role')
        if self.instructor and course and role:
            if InstructorCourseAssignment.objects.filter(
                instructor=self.instructor, course=course, role=role
            ).exists():
                raise forms.ValidationError(
                    'This instructor is already assigned to that course in this role.'
                )
        return cleaned


class InstructorObservationForm(forms.ModelForm):
    class Meta:
        model  = InstructorObservation
        fields = [
            'course', 'observation_date', 'session_observed',
            'preparation', 'content_knowledge', 'delivery',
            'student_engagement', 'time_management', 'professionalism',
            'strengths', 'opportunities', 'action_items', 'overall_rating',
        ]
        widgets = {
            'course':            forms.Select(attrs=_fs),
            'observation_date':  forms.DateInput(attrs=_date),
            'session_observed':  forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. EMT Unit 3 — Airway'}),
            'preparation':       forms.Select(attrs=_fs, choices=[('', '—')] + [(i, i) for i in range(1, 6)]),
            'content_knowledge': forms.Select(attrs=_fs, choices=[('', '—')] + [(i, i) for i in range(1, 6)]),
            'delivery':          forms.Select(attrs=_fs, choices=[('', '—')] + [(i, i) for i in range(1, 6)]),
            'student_engagement': forms.Select(attrs=_fs, choices=[('', '—')] + [(i, i) for i in range(1, 6)]),
            'time_management':   forms.Select(attrs=_fs, choices=[('', '—')] + [(i, i) for i in range(1, 6)]),
            'professionalism':   forms.Select(attrs=_fs, choices=[('', '—')] + [(i, i) for i in range(1, 6)]),
            'overall_rating':    forms.Select(attrs=_fs, choices=[('', '—')] + [(i, i) for i in range(1, 6)]),
            'strengths':         forms.Textarea(attrs={**_fc, 'rows': 3}),
            'opportunities':     forms.Textarea(attrs={**_fc, 'rows': 3}),
            'action_items':      forms.Textarea(attrs={**_fc, 'rows': 3}),
        }


class InstructorMeetingForm(forms.ModelForm):
    class Meta:
        model  = InstructorMeeting
        fields = [
            'meeting_date', 'meeting_type', 'topics_discussed',
            'action_items', 'next_meeting_date',
        ]
        widgets = {
            'meeting_date':      forms.DateInput(attrs=_date),
            'meeting_type':      forms.Select(attrs=_fs),
            'topics_discussed':  forms.Textarea(attrs={**_fc, 'rows': 5}),
            'action_items':      forms.Textarea(attrs={**_fc, 'rows': 3}),
            'next_meeting_date': forms.DateInput(attrs=_date),
        }


class RemediationPlanForm(forms.ModelForm):
    class Meta:
        model  = RemediationPlan
        fields = ['issue_identified', 'plan_details', 'target_date', 'retain_until']
        widgets = {
            'issue_identified': forms.Textarea(attrs={**_fc, 'rows': 4}),
            'plan_details':     forms.Textarea(attrs={**_fc, 'rows': 5}),
            'target_date':      forms.DateInput(attrs=_date),
            'retain_until':     forms.DateInput(attrs=_date),
        }


class RemediationUpdateForm(forms.ModelForm):
    class Meta:
        model  = RemediationPlan
        fields = ['status', 'completion_date', 'completion_notes']
        widgets = {
            'status':           forms.Select(attrs=_fs),
            'completion_date':  forms.DateInput(attrs=_date),
            'completion_notes': forms.Textarea(attrs={**_fc, 'rows': 3}),
        }
