from django.apps import AppConfig


def sync_master_admin_after_migrate(sender, **kwargs):
    """Run sync_master_admin after every `migrate`, so the owner's admin login is
    kept in sync no matter which start command Railway uses for this service."""
    import sys

    if sys.argv[1:2] == ["test"]:
        return
    from django.core.management import call_command

    try:
        call_command("sync_master_admin")
    except Exception as exc:  # never block a deploy over this
        print(f"sync_master_admin: skipped after migrate ({type(exc).__name__}: {exc})")


class StudentsConfig(AppConfig):
    name = "students"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(sync_master_admin_after_migrate, sender=self,
                             dispatch_uid="sync_master_admin_after_migrate")
