from django.db.models.signals import post_save
from django.dispatch import receiver
from courses.models import CourseEnrollment


@receiver(post_save, sender=CourseEnrollment)
def create_gradebook_on_enrollment(sender, instance, created, **kwargs):
    if created:
        from grades.models import GradeBook
        GradeBook.objects.get_or_create(
            student=instance.student,
            course=instance.course,
        )
