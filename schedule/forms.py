from django import forms

from .models import CalendarEvent

_fc   = {'class': 'form-control'}
_fs   = {'class': 'form-select'}
_date = {'class': 'form-control', 'type': 'date'}
_time = {'class': 'form-control', 'type': 'time'}


class CalendarEventForm(forms.ModelForm):
    class Meta:
        model  = CalendarEvent
        fields = [
            'course', 'event_type', 'title', 'description',
            'date', 'all_day', 'start_time', 'end_time', 'location',
        ]
        widgets = {
            'course':      forms.Select(attrs=_fs),
            'event_type':  forms.Select(attrs=_fs),
            'title':       forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. Unit 3 Exam'}),
            'description': forms.Textarea(attrs={**_fc, 'rows': 3}),
            'date':        forms.DateInput(attrs=_date),
            'start_time':  forms.TimeInput(attrs=_time),
            'end_time':    forms.TimeInput(attrs=_time),
            'location':    forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. Station 1 Training Room'}),
        }

    def __init__(self, courses_queryset, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].queryset = courses_queryset
        self.fields['course'].label_from_instance = lambda c: f'Option {c.option_number} — {c.name}'
        self.fields['all_day'].widget.attrs['class'] = 'form-check-input'

    def clean(self):
        cleaned = super().clean()
        all_day = cleaned.get('all_day')
        start   = cleaned.get('start_time')
        end     = cleaned.get('end_time')
        if not all_day and not start:
            raise forms.ValidationError('Enter a start time, or mark this event as all-day.')
        if start and end and end <= start:
            raise forms.ValidationError('End time must be after start time.')
        return cleaned


class CalendarCopyForm(forms.Form):
    """Pick a past course's calendar to reuse for a new course."""

    source = forms.ModelChoiceField(
        queryset=None, label='Copy calendar from',
        widget=forms.Select(attrs=_fs),
    )
    target = forms.ModelChoiceField(
        queryset=None, label='Copy calendar to',
        widget=forms.Select(attrs=_fs),
    )
    new_start = forms.DateField(
        label='First class session of the new course',
        widget=forms.DateInput(attrs=_date),
    )

    def __init__(self, *args, **kwargs):
        from courses.models import Course
        super().__init__(*args, **kwargs)
        label = lambda c: f'Option {c.option_number} — {c.name}'
        self.fields['source'].queryset = (
            Course.objects.filter(calendar_events__isnull=False).distinct().order_by('option_number')
        )
        self.fields['target'].queryset = Course.objects.filter(is_active=True).order_by('option_number')
        self.fields['source'].label_from_instance = label
        self.fields['target'].label_from_instance = label

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('source') and cleaned.get('source') == cleaned.get('target'):
            raise forms.ValidationError('Pick two different courses.')
        return cleaned
