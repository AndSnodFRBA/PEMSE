"""Keep the owner's admin login the same across every Four Line project.

Set two Railway variables on this service (use the same values on every project):

    MASTER_ADMIN_EMAIL     your sign-in email (also used as the username)
    MASTER_ADMIN_PASSWORD  your password

On each deploy this creates that account if it's missing, or updates it: full
admin access, username set to the email, and the password set to
MASTER_ADMIN_PASSWORD. If the password already matches, it isn't rewritten, so
deploys don't sign you out. If either variable is missing, nothing happens.
This command never stops a deploy; problems are only printed to the log.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

# Extra admin flags this project uses on top of is_staff / is_superuser.
EXTRA_FIELDS = {"role": "admin"}


class Command(BaseCommand):
    help = "Create or update the owner's admin account from MASTER_ADMIN_EMAIL / MASTER_ADMIN_PASSWORD."

    def handle(self, *args, **options):
        email = os.environ.get("MASTER_ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("MASTER_ADMIN_PASSWORD", "")
        if not email or not password:
            self.stdout.write("sync_master_admin: MASTER_ADMIN_EMAIL / MASTER_ADMIN_PASSWORD not set, skipping.")
            return
        try:
            with transaction.atomic():
                self._sync(email, password)
        except Exception as exc:  # never block a deploy over this
            self.stderr.write(f"sync_master_admin: could not update the admin account ({type(exc).__name__}: {exc})")

    def _sync(self, email, password):
        User = get_user_model()
        field_names = {f.name for f in User._meta.get_fields()}
        login_field = User.USERNAME_FIELD

        # Find the existing account: by email first, then by login name.
        users = User._default_manager.all()
        candidates = list(users.filter(email__iexact=email).order_by("-is_superuser", "pk")[:1])
        if not candidates and login_field != "email":
            candidates = list(users.filter(**{f"{login_field}__iexact": email})[:1])
        user = candidates[0] if candidates else None
        created = user is None
        if created:
            user = User(**{login_field: email})

        changes = []

        def put(name, value):
            if name in field_names and getattr(user, name) != value:
                setattr(user, name, value)
                changes.append(name)

        put("email", email)
        if "username" in field_names and user.username != email:
            taken = users.filter(username__iexact=email).exclude(pk=user.pk).exists()
            if taken:
                self.stdout.write(f"sync_master_admin: another account already uses the username {email}; leaving the username as {user.username!r}.")
            else:
                put("username", email)
        put("is_active", True)
        put("is_staff", True)
        put("is_superuser", True)
        for name, value in EXTRA_FIELDS.items():
            put(name, value)

        if created or not user.has_usable_password() or not user.check_password(password):
            user.set_password(password)
            changes.append("password")

        if created:
            user.save()
            self.stdout.write(self.style.SUCCESS(f"sync_master_admin: created admin account {email}."))
        elif changes:
            user.save()
            self.stdout.write(self.style.SUCCESS(f"sync_master_admin: updated {email} ({', '.join(sorted(set(changes)))})."))
        else:
            self.stdout.write(f"sync_master_admin: {email} is already up to date.")
