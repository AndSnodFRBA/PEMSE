"""python manage.py send_reminders [--dry-run]

Intended to run daily via an external scheduler (Railway Cron Job). Idempotent —
each rule enforces its own cooldown/once-only logic via ReminderLog, so running
this more than once on the same day is safe.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from students.reminders import REMINDER_RULES, run_rule


class Command(BaseCommand):
    help = 'Check all reminder rules and email students who are due. Idempotent — safe to run daily.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report who would be emailed without sending or logging.',
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        dry_run = options['dry_run']
        for rule in REMINDER_RULES:
            count = run_rule(rule, today, dry_run=dry_run)
            suffix = ' (dry run)' if dry_run else ''
            self.stdout.write(f'{rule.key}: {count} reminder(s){suffix}')
