from django import forms
from django.utils import timezone

from documents.models import InstructorDocument
from students.models import Student
from .models import (
    AttendanceRecord,
    InstructionalHourLog,
    StudentAttendance,
)

_fc   = {'class': 'form-control'}
_fs   = {'class': 'form-select'}
_date = {'class': 'form-control', 'type': 'date'}
_time = {'class': 'form-control', 'type': 'time'}


class HourLogForm(forms.ModelForm):
    class Meta:
        model  = InstructionalHourLog
        fields = [
            'course', 'session_date', 'start_time', 'end_time',
            'session_type', 'topic_covered', 'students_present',
            'location', 'notes',
        ]
        widgets = {
            'course':           forms.Select(attrs=_fs),
            'session_date':     forms.DateInput(attrs=_date),
            'start_time':       forms.TimeInput(attrs=_time),
            'end_time':         forms.TimeInput(attrs=_time),
            'session_type':     forms.Select(attrs=_fs),
            'topic_covered':    forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. Patient Assessment, Airway Management'}),
            'students_present': forms.NumberInput(attrs={**_fc, 'min': '0'}),
            'location':         forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. Station 1 Training Room'}),
            'notes':            forms.Textarea(attrs={**_fc, 'rows': 3}),
        }

    def __init__(self, instructor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import InstructorCourseAssignment
        assigned_course_ids = InstructorCourseAssignment.objects.filter(
            instructor=instructor, is_active=True
        ).values_list('course_id', flat=True)
        from courses.models import Course
        self.fields['course'].queryset = Course.objects.filter(pk__in=assigned_course_ids)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_time')
        end   = cleaned.get('end_time')
        if start and end and end <= start:
            raise forms.ValidationError('End time must be after start time.')
        if start and end:
            from datetime import datetime, date
            td = datetime.combine(date.today(), end) - datetime.combine(date.today(), start)
            cleaned['hours'] = round(td.seconds / 3600, 2)
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        cleaned = self.cleaned_data
        start = cleaned.get('start_time')
        end   = cleaned.get('end_time')
        if start and end:
            from datetime import datetime, date
            td = datetime.combine(date.today(), end) - datetime.combine(date.today(), start)
            instance.hours = round(td.seconds / 3600, 2)
        if commit:
            instance.save()
        return instance


class AttendanceSessionForm(forms.ModelForm):
    class Meta:
        model  = AttendanceRecord
        fields = [
            'course', 'calendar_event', 'session_date', 'session_type', 'session_topic',
            'session_start', 'session_end', 'notes',
        ]
        widgets = {
            'course':         forms.Select(attrs=_fs),
            'calendar_event': forms.Select(attrs=_fs),
            'session_date':   forms.DateInput(attrs=_date),
            'session_type':   forms.Select(attrs=_fs),
            'session_topic':  forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. Airway Management'}),
            'session_start':  forms.TimeInput(attrs=_time),
            'session_end':    forms.TimeInput(attrs=_time),
            'notes':          forms.Textarea(attrs={**_fc, 'rows': 2}),
        }

    def __init__(self, instructor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import InstructorCourseAssignment
        assigned_course_ids = InstructorCourseAssignment.objects.filter(
            instructor=instructor, is_active=True
        ).values_list('course_id', flat=True)
        from courses.models import Course
        self.fields['course'].queryset = Course.objects.filter(pk__in=assigned_course_ids)

        from schedule.models import CalendarEvent
        self.fields['calendar_event'].queryset = CalendarEvent.objects.filter(
            course_id__in=assigned_course_ids,
            event_type=CalendarEvent.EventType.SESSION,
            date__gte=timezone.now().date(),
        ).order_by('date')
        self.fields['calendar_event'].required = False
        self.fields['calendar_event'].label = 'Link to scheduled class (optional)'


class StudentAttendanceForm(forms.ModelForm):
    class Meta:
        model  = StudentAttendance
        fields = ['status', 'arrival_time', 'notes']
        widgets = {
            'status':       forms.Select(attrs=_fs),
            'arrival_time': forms.TimeInput(attrs=_time),
            'notes':        forms.TextInput(attrs={**_fc, 'placeholder': 'Optional note…'}),
        }


class InstructorProfileForm(forms.ModelForm):
    class Meta:
        model  = Student
        fields = [
            'first_name', 'last_name', 'phone', 'email',
            'address', 'city', 'state', 'zip_code',
            'instructor_license_number', 'instructor_license_level',
            'instructor_license_expiry', 'instructor_certifications',
            'instructor_bio', 'instructor_employer',
            'instructor_employer_address', 'instructor_years_experience',
        ]
        widgets = {
            'first_name':                  forms.TextInput(attrs=_fc),
            'last_name':                   forms.TextInput(attrs=_fc),
            'phone':                       forms.TextInput(attrs=_fc),
            'email':                       forms.EmailInput(attrs=_fc),
            'address':                     forms.TextInput(attrs=_fc),
            'city':                        forms.TextInput(attrs=_fc),
            'state':                       forms.TextInput(attrs={**_fc, 'maxlength': '2'}),
            'zip_code':                    forms.TextInput(attrs=_fc),
            'instructor_license_number':   forms.TextInput(attrs=_fc),
            'instructor_license_level':    forms.Select(attrs=_fs),
            'instructor_license_expiry':   forms.DateInput(attrs=_date),
            'instructor_certifications':   forms.TextInput(attrs={**_fc, 'placeholder': 'ACLS, PALS, ITLS…'}),
            'instructor_bio':              forms.Textarea(attrs={**_fc, 'rows': 4}),
            'instructor_employer':         forms.TextInput(attrs=_fc),
            'instructor_employer_address': forms.TextInput(attrs=_fc),
            'instructor_years_experience': forms.NumberInput(attrs={**_fc, 'min': '0'}),
        }


class InstructorDocumentForm(forms.ModelForm):
    class Meta:
        model  = InstructorDocument
        fields = ['title', 'description', 'course', 'file']
        widgets = {
            'title':       forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. Student Handbook'}),
            'description': forms.TextInput(attrs={**_fc, 'placeholder': 'Optional short note'}),
            'course':      forms.Select(attrs=_fs),
            'file':        forms.ClearableFileInput(attrs=_fc),
        }

    def __init__(self, instructor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import InstructorCourseAssignment
        assigned_course_ids = InstructorCourseAssignment.objects.filter(
            instructor=instructor, is_active=True
        ).values_list('course_id', flat=True)
        from courses.models import Course
        self.fields['course'].queryset = Course.objects.filter(pk__in=assigned_course_ids)
        self.fields['course'].required = False
        self.fields['course'].empty_label = 'All students (not course-specific)'
