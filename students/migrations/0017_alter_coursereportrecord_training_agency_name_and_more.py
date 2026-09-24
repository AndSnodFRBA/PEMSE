# Placeholder that keeps PEMSE's migration graph aligned with the EMS Training
# Zone fork. In that fork, 0017 swapped the SiteSettings/CourseReportRecord
# defaults to its own agency's values; PEMSE keeps its original defaults, so
# there is nothing to change here. Later migrations (0018+) depend on this name.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0016_sitesettings'),
    ]

    operations = []
