### forms.py
from django import forms

EXPIRING_DOC_TYPE_SLUGS = ('cpr-card', 'professional-lic')


class DocumentUploadForm(forms.Form):
    file = forms.FileField(
        label='Select file',
        help_text='Accepted: PDF, JPG, PNG — max 10 MB'
    )

    def __init__(self, *args, doc_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        if doc_type and doc_type.slug in EXPIRING_DOC_TYPE_SLUGS:
            self.fields['expiration_date'] = forms.DateField(
                label='Expiration date',
                required=False,
                widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                help_text='When does this card/license expire?',
            )
