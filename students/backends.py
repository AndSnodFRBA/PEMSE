from django.contrib.auth.backends import ModelBackend
from .models import Student


class EmailBackend(ModelBackend):
    """Authenticate using email address instead of username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = Student.objects.get(email__iexact=username)
        except Student.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
