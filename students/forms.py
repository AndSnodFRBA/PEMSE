from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from evaluations.phi_filter import scan_for_phi
from .models import PatientContactRecord, Student, PaymentRecord

_fc = {'class': 'form-control'}
_fs = {'class': 'form-select'}


class StudentLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email address',
        widget=forms.EmailInput(attrs={'placeholder': 'jane@email.com', 'autofocus': True})
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'})
    )


class StudentRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=100, label='First name')
    last_name  = forms.CharField(max_length=100, label='Last name')
    email      = forms.EmailField(label='Email address')
    password1  = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'placeholder': 'Min. 8 characters'}))
    password2  = forms.CharField(label='Confirm password', widget=forms.PasswordInput(attrs={'placeholder': 'Repeat password'}))

    class Meta:
        model = Student
        fields = ['first_name', 'last_name', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if Student.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        student = super().save(commit=False)
        student.username = self.cleaned_data['email'].lower()
        student.email    = self.cleaned_data['email'].lower()
        if commit:
            student.save()
        return student


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'first_name', 'last_name', 'phone', 'ok_to_text',
            'address', 'city', 'state', 'zip_code', 'date_of_birth',
            'profile_photo',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'ok_to_text': forms.Select(choices=[(True, 'Yes'), (False, 'No')]),
            'profile_photo': forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/gif'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'profile_photo':
                field.widget.attrs.setdefault('class', 'form-control')

    def clean_profile_photo(self):
        photo = self.cleaned_data.get('profile_photo')
        if photo and hasattr(photo, 'content_type'):
            if photo.content_type not in ('image/jpeg', 'image/png', 'image/gif'):
                raise forms.ValidationError('Please upload a JPG, PNG, or GIF image.')
            if photo.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Photo must be smaller than 5MB.')
        return photo


class PaymentForm(forms.ModelForm):
    class Meta:
        model = PaymentRecord
        fields = [
            'method', 'pay_option', 'check_number',
            'dept_name', 'dept_address', 'dept_contact',
            'dept_email', 'dept_phone',
        ]
        widgets = {
            'dept_address': forms.Textarea(attrs={'rows': 2}),
        }


class StudentPatientContactForm(forms.ModelForm):
    """Student logs their own patient contact — held as unverified until a
    staff member or instructor signs off (see students.models.PatientContactRecord)."""
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
            'contact_date':              forms.DateInput(attrs={**_fc, 'type': 'date'}),
            'site_name':                 forms.TextInput(attrs=_fc),
            'contact_type':              forms.Select(attrs=_fs),
            'supervisor_name':           forms.TextInput(attrs=_fc),
            'supervisor_license_level':  forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. NREMT-P'}),
            'patient_age_group':         forms.Select(attrs=_fs),
            'chief_complaint':           forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. Chest pain, no identifying details'}),
            'notes':                     forms.Textarea(attrs={**_fc, 'rows': 2}),
        }
        help_texts = {
            'chief_complaint': 'De-identified only — no patient names, dates of birth, or other identifying details.',
        }

    def _clean_text_field(self, name):
        value = self.cleaned_data.get(name, '')
        issues = scan_for_phi(value)
        if issues:
            raise forms.ValidationError(issues)
        return value

    def clean_chief_complaint(self): return self._clean_text_field('chief_complaint')
    def clean_notes(self):           return self._clean_text_field('notes')
