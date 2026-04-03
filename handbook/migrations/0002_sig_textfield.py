from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('handbook', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='handbookacknowledgment',
            name='sig_name',
            field=models.TextField(),
        ),
    ]
