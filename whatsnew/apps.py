from django.apps import AppConfig


def draft_after_migrate(sender, **kwargs):
    """After every `migrate` (which every deploy runs), turn this deploy's commit
    into a draft What's New note for the owner to review."""
    import sys

    if sys.argv[1:2] == ["test"]:
        return
    from django.core.management import call_command

    try:
        call_command("draft_whats_new")
    except Exception as exc:  # never block a deploy over this
        print(f"draft_whats_new: skipped ({type(exc).__name__}: {exc})")


class WhatsNewConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "whatsnew"
    verbose_name = "What's New"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(draft_after_migrate, sender=self, dispatch_uid="whatsnew_draft_after_migrate")
