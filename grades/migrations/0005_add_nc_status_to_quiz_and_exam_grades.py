from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0004_remove_gradebook_fisdap_attempt_1_and_more'),
    ]

    operations = [
        # QuizGrade: add status, make score nullable
        migrations.AddField(
            model_name='quizgrade',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[('completed', 'Completed'), ('not_completed', 'Not Completed Yet')],
                default='completed',
                help_text='Use "Not Completed Yet" for assignments not yet taken',
            ),
        ),
        migrations.AlterField(
            model_name='quizgrade',
            name='score',
            field=models.DecimalField(
                max_digits=5, decimal_places=2, null=True, blank=True,
            ),
        ),
        # SectionExamGrade: add status, make score nullable
        migrations.AddField(
            model_name='sectionexamgrade',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[('completed', 'Completed'), ('not_completed', 'Not Completed Yet')],
                default='completed',
                help_text='Use "Not Completed Yet" for exams not yet taken',
            ),
        ),
        migrations.AlterField(
            model_name='sectionexamgrade',
            name='score',
            field=models.DecimalField(
                max_digits=5, decimal_places=2, null=True, blank=True,
            ),
        ),
    ]
