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
