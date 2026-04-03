"""
python manage.py seed_courses

Seeds the 7 PEMSE 2025 courses exactly as they appear on the registration form.
Safe to re-run — uses update_or_create.
"""
from django.core.management.base import BaseCommand
from courses.models import Course

DEFAULT_LOCATION = {
    'location_address': '709 Rosedale Dr.',
    'location_city':    'Scottsbluff',
    'location_state':   'NE',
}

COURSES = [
    dict(option_number=1, tag='EMR',    tag_color='#0a6b47', tag_bg='#d8f5ec',
         licensure='EMR',
         name='EMR Hybrid Course',        description='With physical textbook included.',
         price=750,  min_down=750,  includes_shirt=False,
         **DEFAULT_LOCATION),
    dict(option_number=2, tag='EMR',    tag_color='#0a6b47', tag_bg='#d8f5ec',
         licensure='EMR',
         name='EMR Hybrid Course',        description='No physical book — digital access.',
         price=650,  min_down=650,  includes_shirt=False,
         **DEFAULT_LOCATION),
    dict(option_number=3, tag='EMT',    tag_color='#1557a0', tag_bg='#dde9f8',
         licensure='EMT',
         name='EMT Hybrid Course',        description='With physical textbook included.',
         price=1300, min_down=700,  includes_shirt=False,
         **DEFAULT_LOCATION),
    dict(option_number=4, tag='EMT',    tag_color='#1557a0', tag_bg='#dde9f8',
         licensure='EMT',
         name='EMT Hybrid Course',        description='No physical book — digital access.',
         price=1100, min_down=600,  includes_shirt=False,
         **DEFAULT_LOCATION),
    dict(option_number=5, tag='AEMT',   tag_color='#8b3020', tag_bg='#fce8e4',
         licensure='AEMT',
         name='EMT to AEMT Hybrid Bridge', description='No physical book. Polo shirt included. Requires active EMT-B.',
         price=1200, min_down=700,  includes_shirt=True,
         **DEFAULT_LOCATION),
    dict(option_number=6, tag='Bridge', tag_color='#854f0b', tag_bg='#faeeda',
         licensure='EMT',
         name='RN/LPN to EMT Hybrid Bridge', description='No physical book. For licensed RNs and LPNs.',
         price=1100, min_down=600,  includes_shirt=False,
         **DEFAULT_LOCATION),
    dict(option_number=7, tag='CE',     tag_color='#3a6610', tag_bg='#e5f3d8',
         licensure='CE',
         name='EMT IV Therapy',           description='Textbook and lab fees included.',
         price=200,  min_down=200,  includes_shirt=False,
         **DEFAULT_LOCATION),
]


class Command(BaseCommand):
    help = 'Seed the 7 PEMSE 2025 courses'

    def handle(self, *args, **kwargs):
        for i, data in enumerate(COURSES):
            obj, created = Course.objects.update_or_create(
                option_number=data['option_number'],
                defaults={**data, 'order': i, 'is_active': True}
            )
            verb = 'Created' if created else 'Updated'
            self.stdout.write(f'{verb}: Option {obj.option_number} — {obj.name} (${obj.price})')
        self.stdout.write(self.style.SUCCESS(f'\n✓ {len(COURSES)} courses seeded.'))
