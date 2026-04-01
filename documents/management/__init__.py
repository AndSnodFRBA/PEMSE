"""python manage.py seed_documents"""
from django.core.management.base import BaseCommand
from documents.models import DocumentType

DOCS = [
    dict(slug='drivers-license',   label="Copy of driver's license",      hint="Clear photo or scan of your current driver's license",                    required=True,  icon_color='#854f0b', icon_bg='#faeeda', order=1),
    dict(slug='cpr-card',          label="AHA HCP CPR card",               hint="American Heart Association Healthcare Provider — upload front & back",     required=True,  icon_color='#1557a0', icon_bg='#dde9f8', order=2),
    dict(slug='immunization',      label="Immunization records",            hint="Up-to-date vaccination documentation (Hep B, Tdap, flu recommended)",     required=True,  icon_color='#0a6b47', icon_bg='#d8f5ec', order=3),
    dict(slug='professional-lic',  label="RN / LPN / EMT license",         hint="Required for bridge courses (Options 5 & 6). Current license only.",      required=False, icon_color='#7b3fa0', icon_bg='#f8f0fb', order=4),
]


class Command(BaseCommand):
    help = 'Seed required document types'

    def handle(self, *args, **kwargs):
        for data in DOCS:
            obj, created = DocumentType.objects.update_or_create(
                slug=data['slug'], defaults=data
            )
            verb = 'Created' if created else 'Updated'
            self.stdout.write(f'{verb}: {obj.label}')
        self.stdout.write(self.style.SUCCESS(f'\n✓ {len(DOCS)} document types seeded.'))
