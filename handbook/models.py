from django.db import models
from django.conf import settings


class HandbookChapter(models.Model):
    """A chapter in the student handbook — editable from Django admin."""
    number     = models.PositiveIntegerField(unique=True)
    title      = models.CharField(max_length=200)
    body       = models.TextField(help_text='Supports basic HTML')
    is_active  = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['number']

    def __str__(self):
        return f'Chapter {self.number}: {self.title}'


class HandbookAcknowledgment(models.Model):
    """Records a student signing the handbook."""
    student    = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='handbook_ack'
    )
    sig_name   = models.CharField(max_length=200)
    signed_at  = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f'{self.student} signed {self.signed_at.strftime("%Y-%m-%d")}'
