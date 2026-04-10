from django import forms

from .models import ClinicalRotation, PreceptorEvaluation, StudentSiteEvaluation

_fc = {'class': 'form-control'}
_fs = {'class': 'form-select'}

RATING_SELECT = [(0, '— Select —')] + [(i, str(i)) for i in range(1, 6)]


class AddRotationForm(forms.ModelForm):
    """Student logs a new rotation and provides preceptor contact info."""

    preceptor_name  = forms.CharField(max_length=200, widget=forms.TextInput(attrs=_fc))
    preceptor_email = forms.EmailField(widget=forms.EmailInput(attrs=_fc))
    preceptor_title = forms.CharField(
        max_length=100, required=False, widget=forms.TextInput(attrs=_fc)
    )

    class Meta:
        model = ClinicalRotation
        fields = [
            'site_name', 'site_address', 'site_city', 'site_type',
            'rotation_date', 'shift_start', 'shift_end',
            'hours_completed', 'patient_contacts', 'course',
        ]
        widgets = {
            'site_name':        forms.TextInput(attrs=_fc),
            'site_address':     forms.TextInput(attrs=_fc),
            'site_city':        forms.TextInput(attrs=_fc),
            'site_type':        forms.Select(attrs=_fs),
            'rotation_date':    forms.DateInput(attrs={**_fc, 'type': 'date'}),
            'shift_start':      forms.TimeInput(attrs={**_fc, 'type': 'time'}),
            'shift_end':        forms.TimeInput(attrs={**_fc, 'type': 'time'}),
            'hours_completed':  forms.NumberInput(attrs={**_fc, 'step': '0.5', 'min': '0'}),
            'patient_contacts': forms.NumberInput(attrs={**_fc, 'min': '0'}),
            'course':           forms.Select(attrs=_fs),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['site_address'].required = False
        self.fields['site_city'].required    = False
        self.fields['shift_start'].required  = False
        self.fields['shift_end'].required    = False
        self.fields['course'].required       = False
        # Move preceptor fields to the end for ordering in template
        for f in ('preceptor_name', 'preceptor_email', 'preceptor_title'):
            self.fields[f].label = {
                'preceptor_name':  'Preceptor name',
                'preceptor_email': 'Preceptor email',
                'preceptor_title': 'Preceptor title / role',
            }[f]


class PreceptorEvalForm(forms.Form):
    """Filled out by the preceptor via the public token link."""

    # ── Professional Behavior ─────────────────────────────────────────────────
    appearance_professional = forms.ChoiceField(choices=RATING_SELECT, widget=forms.Select(attrs=_fs))
    punctuality             = forms.ChoiceField(choices=RATING_SELECT, widget=forms.Select(attrs=_fs))
    communication_patients  = forms.ChoiceField(choices=RATING_SELECT, widget=forms.Select(attrs=_fs))
    communication_team      = forms.ChoiceField(choices=RATING_SELECT, widget=forms.Select(attrs=_fs))
    attitude_motivation     = forms.ChoiceField(choices=RATING_SELECT, widget=forms.Select(attrs=_fs))

    # ── Clinical Skills ───────────────────────────────────────────────────────
    patient_assessment          = forms.ChoiceField(choices=RATING_SELECT, widget=forms.Select(attrs=_fs))
    clinical_skills_performance = forms.ChoiceField(choices=RATING_SELECT, widget=forms.Select(attrs=_fs))
    critical_thinking           = forms.ChoiceField(choices=RATING_SELECT, widget=forms.Select(attrs=_fs))
    medical_knowledge           = forms.ChoiceField(choices=RATING_SELECT, widget=forms.Select(attrs=_fs))
    documentation               = forms.ChoiceField(choices=RATING_SELECT, widget=forms.Select(attrs=_fs))

    # ── Overall ───────────────────────────────────────────────────────────────
    overall_performance = forms.ChoiceField(choices=RATING_SELECT, widget=forms.Select(attrs=_fs))
    recommended_to_pass = forms.ChoiceField(
        choices=[('', '— Select —'), ('true', 'Yes — recommend to pass'), ('false', 'No — does not recommend')],
        widget=forms.Select(attrs=_fs),
    )

    strengths             = forms.CharField(required=False, widget=forms.Textarea(attrs={**_fc, 'rows': 4}))
    areas_for_improvement = forms.CharField(required=False, widget=forms.Textarea(attrs={**_fc, 'rows': 4}))
    additional_comments   = forms.CharField(required=False, widget=forms.Textarea(attrs={**_fc, 'rows': 3}))

    def clean_recommended_to_pass(self):
        val = self.cleaned_data.get('recommended_to_pass')
        if not val:
            raise forms.ValidationError('Please select a recommendation.')
        return val == 'true'

    def _clean_rating(self, name):
        val = self.cleaned_data.get(name)
        try:
            v = int(val)
            if v < 1 or v > 5:
                raise ValueError
            return v
        except (ValueError, TypeError):
            raise forms.ValidationError('Please select a rating.')

    def clean_appearance_professional(self):    return self._clean_rating('appearance_professional')
    def clean_punctuality(self):                return self._clean_rating('punctuality')
    def clean_communication_patients(self):     return self._clean_rating('communication_patients')
    def clean_communication_team(self):         return self._clean_rating('communication_team')
    def clean_attitude_motivation(self):        return self._clean_rating('attitude_motivation')
    def clean_patient_assessment(self):         return self._clean_rating('patient_assessment')
    def clean_clinical_skills_performance(self): return self._clean_rating('clinical_skills_performance')
    def clean_critical_thinking(self):          return self._clean_rating('critical_thinking')
    def clean_medical_knowledge(self):          return self._clean_rating('medical_knowledge')
    def clean_documentation(self):              return self._clean_rating('documentation')
    def clean_overall_performance(self):        return self._clean_rating('overall_performance')


class StudentSiteEvalForm(forms.ModelForm):
    """Student evaluates the clinical site and preceptor after rotation."""

    BOOL_CHOICES = [('', '— Select —'), ('true', 'Yes'), ('false', 'No')]

    site_would_return   = forms.ChoiceField(choices=BOOL_CHOICES, widget=forms.Select(attrs=_fs))
    would_you_recommend = forms.ChoiceField(choices=BOOL_CHOICES, widget=forms.Select(attrs=_fs))

    class Meta:
        model = StudentSiteEvaluation
        fields = [
            'site_organization', 'site_learning_opportunities', 'site_equipment_available',
            'site_patient_volume', 'site_staff_welcoming', 'site_would_return',
            'preceptor_knowledge', 'preceptor_teaching_style', 'preceptor_feedback_quality',
            'preceptor_professionalism', 'preceptor_overall',
            'best_part_of_rotation', 'what_could_be_improved',
            'would_you_recommend', 'additional_comments',
        ]
        widgets = {
            'site_organization':           forms.Select(choices=RATING_SELECT, attrs=_fs),
            'site_learning_opportunities': forms.Select(choices=RATING_SELECT, attrs=_fs),
            'site_equipment_available':    forms.Select(choices=RATING_SELECT, attrs=_fs),
            'site_patient_volume':         forms.Select(choices=RATING_SELECT, attrs=_fs),
            'site_staff_welcoming':        forms.Select(choices=RATING_SELECT, attrs=_fs),
            'preceptor_knowledge':         forms.Select(choices=RATING_SELECT, attrs=_fs),
            'preceptor_teaching_style':    forms.Select(choices=RATING_SELECT, attrs=_fs),
            'preceptor_feedback_quality':  forms.Select(choices=RATING_SELECT, attrs=_fs),
            'preceptor_professionalism':   forms.Select(choices=RATING_SELECT, attrs=_fs),
            'preceptor_overall':           forms.Select(choices=RATING_SELECT, attrs=_fs),
            'best_part_of_rotation':       forms.Textarea(attrs={**_fc, 'rows': 4}),
            'what_could_be_improved':      forms.Textarea(attrs={**_fc, 'rows': 4}),
            'additional_comments':         forms.Textarea(attrs={**_fc, 'rows': 3}),
        }

    def clean_site_would_return(self):
        val = self.cleaned_data.get('site_would_return')
        if val == '':
            return None
        return val == 'true'

    def clean_would_you_recommend(self):
        val = self.cleaned_data.get('would_you_recommend')
        if val == '':
            return None
        return val == 'true'

    def _clean_rating(self, name):
        val = self.cleaned_data.get(name)
        if val is None or val == 0:
            return None
        try:
            v = int(val)
            return v if 1 <= v <= 5 else None
        except (ValueError, TypeError):
            return None

    def clean_site_organization(self):           return self._clean_rating('site_organization')
    def clean_site_learning_opportunities(self): return self._clean_rating('site_learning_opportunities')
    def clean_site_equipment_available(self):    return self._clean_rating('site_equipment_available')
    def clean_site_patient_volume(self):         return self._clean_rating('site_patient_volume')
    def clean_site_staff_welcoming(self):        return self._clean_rating('site_staff_welcoming')
    def clean_preceptor_knowledge(self):         return self._clean_rating('preceptor_knowledge')
    def clean_preceptor_teaching_style(self):    return self._clean_rating('preceptor_teaching_style')
    def clean_preceptor_feedback_quality(self):  return self._clean_rating('preceptor_feedback_quality')
    def clean_preceptor_professionalism(self):   return self._clean_rating('preceptor_professionalism')
    def clean_preceptor_overall(self):           return self._clean_rating('preceptor_overall')
