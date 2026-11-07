import os
from io import StringIO
from unittest import mock

from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase

ENV = {"MASTER_ADMIN_EMAIL": "Owner@Example.com", "MASTER_ADMIN_PASSWORD": "master-pass-123"}


def run():
    out = StringIO()
    call_command("sync_master_admin", stdout=out, stderr=out)
    return out.getvalue()


class SyncMasterAdminTests(TestCase):
    def test_skips_without_variables(self):
        with mock.patch.dict(os.environ, {"MASTER_ADMIN_EMAIL": "", "MASTER_ADMIN_PASSWORD": ""}):
            self.assertIn("skipping", run())
        self.assertFalse(get_user_model().objects.filter(email__iexact="owner@example.com").exists())

    def test_creates_admin_then_leaves_matching_password_alone(self):
        with mock.patch.dict(os.environ, ENV):
            self.assertIn("created", run())
            user = get_user_model().objects.get(email="owner@example.com")
            self.assertTrue(user.is_superuser and user.is_staff and user.is_active)
            self.assertTrue(user.check_password("master-pass-123"))
            old_hash = user.password
            self.assertIn("up to date", run())
            user.refresh_from_db()
            self.assertEqual(user.password, old_hash)  # no sign-out on every deploy

    def test_updates_existing_account_found_by_email(self):
        User = get_user_model()
        fields = {"email": "owner@example.com", "password": "old-pass-999"}
        if "username" in {f.name for f in User._meta.get_fields()}:
            fields["username"] = "andrew"
        User.objects.create_user(**fields)
        with mock.patch.dict(os.environ, ENV):
            self.assertIn("updated", run())
        self.assertEqual(User.objects.filter(email__iexact="owner@example.com").count(), 1)
        user = User.objects.get(email="owner@example.com")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("master-pass-123"))
        if "username" in {f.name for f in User._meta.get_fields()}:
            self.assertEqual(user.username, "owner@example.com")

    def test_can_sign_in_with_email_and_master_password(self):
        with mock.patch.dict(os.environ, ENV):
            run()
        request = RequestFactory().post("/login/")
        user = authenticate(request, username="owner@example.com", password="master-pass-123")
        self.assertIsNotNone(user)
        self.assertTrue(user.is_superuser)

    def test_runs_after_migrate_whatever_the_start_command(self):
        from django.db.models.signals import post_migrate

        from students.apps import sync_master_admin_after_migrate

        self.assertTrue(any(r[0][0] == "sync_master_admin_after_migrate" for r in post_migrate.receivers))
        with mock.patch.dict(os.environ, ENV), mock.patch("sys.argv", ["manage.py", "migrate"]):
            sync_master_admin_after_migrate(sender=None)
        self.assertTrue(get_user_model().objects.get(email="owner@example.com").is_superuser)
