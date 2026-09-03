from django.db import migrations

EMAIL = 'gupton.ems@gmail.com'
PHONE = '402-880-8203'
PHONE_PLACEHOLDER = 'Available upon request'


def set_contact_info(apps, schema_editor):
    """Populate the agency contact email/phone on the SiteSettings singleton so
    portal emails can show a real "contact us" line. Only fills values that are
    still blank or at their placeholder default — never overwrites something
    staff have set in Staff > Settings > Site Settings."""
    SiteSettings = apps.get_model('students', 'SiteSettings')
    obj, _ = SiteSettings.objects.get_or_create(pk=1)
    changed = False
    if not (obj.agency_email or '').strip():
        obj.agency_email = EMAIL
        changed = True
    if not (obj.agency_phone or '').strip() or obj.agency_phone.strip() == PHONE_PLACEHOLDER:
        obj.agency_phone = PHONE
        changed = True
    if changed:
        obj.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0019_student_dashboard_intro_dismissed'),
    ]

    operations = [
        migrations.RunPython(set_contact_info, noop),
    ]
