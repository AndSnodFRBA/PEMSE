from django.db import migrations, models


def set_staff_role(apps, schema_editor):
    Student = apps.get_model('students', 'Student')
    Student.objects.filter(is_superuser=True).update(role='staff')
    Student.objects.filter(is_staff=True, is_superuser=False).update(role='staff')


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='role',
            field=models.CharField(
                choices=[('student', 'Student'), ('staff', 'Office Staff')],
                default='student',
                max_length=10,
            ),
        ),
        migrations.RunPython(set_staff_role, migrations.RunPython.noop),
    ]
