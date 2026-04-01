### forms.py
from django import forms

class DocumentUploadForm(forms.Form):
    file = forms.FileField(
        label='Select file',
        help_text='Accepted: PDF, JPG, PNG — max 10 MB'
    )
