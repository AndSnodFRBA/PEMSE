from django.db import migrations


def copy_instructor_notes(apps, schema_editor):
    """One-time copy of legacy per-instructor notes into the shared StudentNote log."""
    StudentNote = apps.get_model('students', 'StudentNote')
    InstructorNote = apps.get_model('instructor', 'InstructorNote')

    for note in InstructorNote.objects.all():
        copied = StudentNote.objects.create(
            student=note.student,
            course=note.course,
            note_type='general',
            body=note.note,
            created_by=note.instructor,
        )
        StudentNote.objects.filter(pk=copied.pk).update(created_at=note.created_at)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0022_studentnote_course'),
        ('instructor', '0003_instructorcourseassignment_can_enter_grades'),
    ]

    operations = [
        migrations.RunPython(copy_instructor_notes, noop_reverse),
    ]
