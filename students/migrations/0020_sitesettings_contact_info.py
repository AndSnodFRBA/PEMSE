from django.db import migrations


class Migration(migrations.Migration):
    """No-op in PEMSE. In the EMS Training Zone fork this migration filled that
    agency's contact email/phone into SiteSettings; PEMSE's SiteSettings row
    already carries its own contact info (editable in Staff > Settings)."""

    dependencies = [
        ('students', '0019_student_dashboard_intro_dismissed'),
    ]

    operations = []
