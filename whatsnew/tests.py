import os
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.template import Context, Template
from django.conf import settings
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .audiences import AUDIENCES, user_audiences
from .models import ReleaseNote, SeenMarker
from .services import unread_notes


def make_user(email, **extra):
    User = get_user_model()
    fields = {"email": email, "password": "pw-123456789"}
    if "username" in {f.name for f in User._meta.get_fields()}:
        fields["username"] = email
    fields.update(extra)
    return User.objects.create_user(**fields)


def publish(title, audience="all", when=None):
    note = ReleaseNote.objects.create(title=title, body="Line one\n\n- first\n- second", audience=audience,
                                      status=ReleaseNote.PUBLISHED)
    if when:
        ReleaseNote.objects.filter(pk=note.pk).update(published_at=when)
    return note


# Pages are rendered without running collectstatic, so use plain static storage.
PLAIN_STATIC = override_settings(STORAGES={
    **getattr(settings, "STORAGES", {}),
    "default": getattr(settings, "STORAGES", {}).get("default", {"BACKEND": "django.core.files.storage.FileSystemStorage"}),
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})


@PLAIN_STATIC
class WhatsNewTests(TestCase):
    def setUp(self):
        self.user = make_user("member@example.com")

    def render_popup(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return Template("{% load whatsnew %}{% whatsnew_popup %}").render(Context({"request": request}))

    def test_first_visit_sets_a_starting_point_without_old_notes(self):
        publish("Old news")
        self.assertEqual(unread_notes(self.user), [])
        self.assertTrue(SeenMarker.objects.filter(user=self.user).exists())

    def test_popup_shows_new_notes_once(self):
        SeenMarker.objects.create(user=self.user, seen_at=timezone.now() - timedelta(days=3))
        publish("Faster search")
        html = self.render_popup(self.user)
        self.assertIn("Faster search", html)
        self.assertIn("<li>first</li>", html)
        self.assertNotIn("Faster search", self.render_popup(self.user))

    def test_drafts_and_hidden_notes_are_never_shown(self):
        SeenMarker.objects.create(user=self.user, seen_at=timezone.now() - timedelta(days=3))
        ReleaseNote.objects.create(title="Secret draft", status=ReleaseNote.DRAFT)
        ReleaseNote.objects.create(title="Hidden one", status=ReleaseNote.HIDDEN)
        self.assertEqual(unread_notes(self.user), [])

    def test_audience_limits_who_sees_a_note(self):
        SeenMarker.objects.create(user=self.user, seen_at=timezone.now() - timedelta(days=3))
        other = next((k for k, _ in AUDIENCES if k not in user_audiences(self.user)), None)
        publish("For everyone")
        if other:
            publish("Not for this user", audience=other)
        titles = [n.title for n in unread_notes(self.user)]
        self.assertEqual(titles, ["For everyone"])

    def test_history_page_lists_published_notes(self):
        publish("Visible note")
        ReleaseNote.objects.create(title="Draft note", status=ReleaseNote.DRAFT)
        self.client.force_login(self.user)
        response = self.client.get(reverse("whatsnew:list"))
        self.assertContains(response, "Visible note")
        self.assertNotContains(response, "Draft note")

    def test_signed_out_users_see_nothing(self):
        from django.contrib.auth.models import AnonymousUser
        publish("Anything")
        self.assertEqual(self.render_popup(AnonymousUser()).strip(), "")

    def test_owner_is_told_about_drafts(self):
        owner = make_user("owner@example.com", is_staff=True, is_superuser=True)
        SeenMarker.objects.create(user=owner)
        ReleaseNote.objects.create(title="Needs review", status=ReleaseNote.DRAFT)
        self.assertIn("1 draft note waiting", self.render_popup(owner))

    def test_admin_publish_action(self):
        from django.contrib.admin.sites import site
        from django.contrib.messages.storage.fallback import FallbackStorage

        owner = make_user("owner2@example.com", is_staff=True, is_superuser=True)
        note = ReleaseNote.objects.create(title="Ready", status=ReleaseNote.DRAFT)
        request = RequestFactory().post("/")
        request.user = owner
        request.session = {}
        request._messages = FallbackStorage(request)
        site._registry[ReleaseNote].publish(request, ReleaseNote.objects.filter(pk=note.pk))
        note.refresh_from_db()
        self.assertEqual(note.status, ReleaseNote.PUBLISHED)
        self.assertIsNotNone(note.published_at)

    @override_settings(WHATSNEW_SKIP_PATH_PREFIXES=("/two-step/",))
    def test_popup_waits_on_skipped_pages(self):
        SeenMarker.objects.create(user=self.user, seen_at=timezone.now() - timedelta(days=3))
        publish("After sign-in")
        request = RequestFactory().get("/two-step/code/")
        request.user = self.user
        html = Template("{% load whatsnew %}{% whatsnew_popup %}").render(Context({"request": request}))
        self.assertNotIn("After sign-in", html)
        self.assertIn("After sign-in", self.render_popup(self.user))

    def test_staff_viewing_as_someone_do_not_use_up_their_popup(self):
        staff = make_user("viewer@example.com", is_staff=True, is_superuser=True)
        SeenMarker.objects.create(user=self.user, seen_at=timezone.now() - timedelta(days=3))
        publish("Theirs to see")
        request = RequestFactory().get("/")
        request.user = self.user
        request.real_user = staff
        Template("{% load whatsnew %}{% whatsnew_popup %}").render(Context({"request": request}))
        self.assertIn("Theirs to see", self.render_popup(self.user))


class DraftFromDeployTests(TestCase):
    ENV = {"RAILWAY_GIT_COMMIT_SHA": "abc1234def",
           "RAILWAY_GIT_COMMIT_MESSAGE": "Add a print button to rosters\n\nRosters can now be printed.\n\nCo-Authored-By: Someone <x@y.z>"}

    def run_cmd(self):
        out = StringIO()
        with mock.patch.dict(os.environ, self.ENV), mock.patch("whatsnew.management.commands.draft_whats_new.git", return_value=None):
            call_command("draft_whats_new", stdout=out)
        return out.getvalue()

    def test_drafts_once_per_commit_without_trailers(self):
        self.assertIn("drafted", self.run_cmd())
        note = ReleaseNote.objects.get()
        self.assertEqual(note.status, ReleaseNote.DRAFT)
        self.assertEqual(note.title, "Add a print button to rosters")
        self.assertEqual(note.body, "Rosters can now be printed.")
        self.assertIn("already drafted", self.run_cmd())
        self.assertEqual(ReleaseNote.objects.count(), 1)

    def test_skips_housekeeping_commits(self):
        with mock.patch.dict(os.environ, {**self.ENV, "RAILWAY_GIT_COMMIT_SHA": "999", "RAILWAY_GIT_COMMIT_MESSAGE": "Trigger redeploy"}), \
             mock.patch("whatsnew.management.commands.draft_whats_new.git", return_value=None):
            call_command("draft_whats_new", stdout=StringIO())
        self.assertEqual(ReleaseNote.objects.count(), 0)
