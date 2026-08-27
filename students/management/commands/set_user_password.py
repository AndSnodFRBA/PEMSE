"""
python manage.py set_user_password --email=user@example.com

Sets a user's password non-interactively, reading the new password from the
SET_PASSWORD_VALUE environment variable rather than a CLI arg or getpass()
prompt — getpass() blocks waiting on a real TTY over some remote shells
(e.g. `railway ssh`), and a CLI arg would leak the password into shell
history / process listings. Never prints the password.
"""
import os

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Set a user's password from the SET_PASSWORD_VALUE environment variable."

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)

    def handle(self, *args, **options):
        from students.models import Student

        password = os.environ.get('SET_PASSWORD_VALUE', '')
        if not password:
            raise CommandError('SET_PASSWORD_VALUE environment variable is not set or empty.')

        try:
            user = Student.objects.get(email__iexact=options['email'])
        except Student.DoesNotExist:
            raise CommandError(f'No user found with email {options["email"]!r}')

        user.set_password(password)
        user.save(update_fields=['password'])
        self.stdout.write(self.style.SUCCESS(f'Password updated for {user.email}'))
