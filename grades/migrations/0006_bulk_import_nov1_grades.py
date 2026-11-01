"""
Original import migration — replaced by 0007 after app label fix.
This is now a no-op so Railway can mark it applied and move on.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0005_add_nc_status_to_quiz_and_exam_grades'),
    ]

    operations = []
