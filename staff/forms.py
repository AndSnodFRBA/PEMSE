from django import forms

from courses.models import Course
from documents.models import StudentDocument
from students.models import Announcement, PaymentHistory, Student


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


class CourseForm(forms.ModelForm):
    class Meta:
        model  = Course
        fields = [
            'option_number', 'tag', 'name', 'description', 'licensure',
            'price', 'min_down', 'includes_shirt', 'is_active',
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
