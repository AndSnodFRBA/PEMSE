from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0002_student_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='student',
            name='contract_sig_name',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='student',
            name='handbook_sig_name',
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name='PaymentHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=8)),
                ('payment_date', models.DateField()),
                ('method', models.CharField(choices=[('cash', 'Cash'), ('check', 'Check'), ('card', 'Card'), ('dept', 'Department')], max_length=20)),
                ('check_number', models.CharField(blank=True, max_length=50)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recorded_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='payments_recorded',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payment_history',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-payment_date']},
        ),
    ]
