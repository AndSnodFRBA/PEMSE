"""python manage.py backup_database [--trigger deploy|scheduled|manual]

Dumps the full database to gzipped JSON and saves it via the default file
storage (S3 in production, media/backups/ locally). Intended to run before
every deploy's migrate step, plus once daily via an external scheduler
(Railway Cron Job) — never raises, so a backup failure can never block a
deploy or a scheduled run.
"""
import gzip
import io
import logging

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)

EXCLUDED_APPS = ['contenttypes', 'auth.permission', 'sessions.session', 'admin.logentry']
KEEP_BACKUPS  = 60  # roughly 2 months of daily backups plus deploy-triggered ones


class Command(BaseCommand):
    help = ('Dump the full database to JSON and upload it to storage (S3 in production, '
            'media/backups/ locally). Never raises — a backup failure must never block a deploy.')

    def add_arguments(self, parser):
        parser.add_argument('--trigger', default='manual', choices=['deploy', 'scheduled', 'manual'])

    def handle(self, *args, **options):
        try:
            self._run(options['trigger'])
        except Exception:
            logger.exception('Database backup failed')
            self.stderr.write(self.style.WARNING('Backup failed — continuing anyway (see logs).'))

    def _run(self, trigger):
        buf = io.StringIO()
        call_command('dumpdata', exclude=EXCLUDED_APPS, use_natural_foreign_keys=True, stdout=buf)

        gz_buf = io.BytesIO()
        with gzip.GzipFile(fileobj=gz_buf, mode='wb') as gz:
            gz.write(buf.getvalue().encode('utf-8'))

        name = f'backups/{trigger}-{timezone.now():%Y%m%d-%H%M%S}.json.gz'
        saved_name = default_storage.save(name, ContentFile(gz_buf.getvalue()))
        self.stdout.write(self.style.SUCCESS(
            f'Backup saved: {saved_name} ({default_storage.size(saved_name):,} bytes)'
        ))
        self._prune_old_backups()

    def _prune_old_backups(self):
        try:
            _dirs, files = default_storage.listdir('backups')
        except FileNotFoundError:
            return
        files = sorted(files)  # filenames are timestamp-sortable
        for old in files[:-KEEP_BACKUPS]:
            default_storage.delete(f'backups/{old}')
