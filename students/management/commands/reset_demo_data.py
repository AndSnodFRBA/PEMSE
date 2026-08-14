from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Reset all demo data — wipes all students, grades, attendance and re-seeds'

    def handle(self, *args, **kwargs):
        from django.conf import settings
        if not settings.DEMO_MODE:
            self.stderr.write(self.style.ERROR(
                'This command only runs when DEMO_MODE=True. Refusing.'
            ))
            return

        from students.models import Student
        # Delete all demo students, instructors (not superusers)
        deleted = Student.objects.filter(
            is_superuser=False
        ).delete()
        self.stdout.write(f'Deleted: {deleted}')

        # Re-seed
        from django.core.management import call_command
        call_command('seed_courses')
        call_command('seed_handbook')
        call_command('seed_documents')
        call_command('seed_emt_hybrid_schedule')
        call_command('seed_demo_data')
        self.stdout.write(self.style.SUCCESS('Demo data reset complete.'))
