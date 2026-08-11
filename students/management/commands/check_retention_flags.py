from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from students.models import CourseCompletionRecord


class Command(BaseCommand):
    help = 'Flag records whose 5-year retention period ends within 90 days'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        approaching = today + timedelta(days=90)
        flagged = CourseCompletionRecord.objects.filter(
            retain_until__lte=approaching, retain_until__gte=today,
            records_flagged_for_review=False,
        ).update(records_flagged_for_review=True)
        self.stdout.write(self.style.SUCCESS(f'Flagged {flagged} records approaching retention end'))
