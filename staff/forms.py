from django import forms

from documents.models import StudentDocument
from students.models import Announcement, Student


class InvitationForm(forms.Form):
    email = forms.EmailField(
        label='Student email address',
        widget=forms.EmailInput(attrs={'placeholder': 'student@email.com', 'class': 'form-control'}),
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
