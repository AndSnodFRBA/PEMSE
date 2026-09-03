"""
python manage.py grant_superuser --email=user@example.com

Gives an existing account full Django admin access (is_staff and
is_superuser), so they can reach every model in /admin/ — including
destructive actions like delete — without needing individually granted
permissions. Intended for a site owner/administrator's own account.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Grant an existing account is_staff and is_superuser so it has full Django admin access."

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)

    def handle(self, *args, **options):
        from students.models import Student

        try:
            user = Student.objects.get(email__iexact=options['email'])
        except Student.DoesNotExist:
            raise CommandError(f'No user found with email {options["email"]!r}')

        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=['is_staff', 'is_superuser'])
        self.stdout.write(self.style.SUCCESS(f'{user.email} is now a Django superuser (is_staff=True, is_superuser=True).'))
