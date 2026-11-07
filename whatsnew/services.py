from django.utils import timezone

from .audiences import is_staff_user, user_audiences
from .models import ReleaseNote, SeenMarker


def visible_notes(user):
    return ReleaseNote.objects.filter(status=ReleaseNote.PUBLISHED, audience__in=user_audiences(user))


def unread_notes(user, mark_seen=False):
    """Published notes for this user since they last saw What's New.

    A user's first visit after this feature ships just records a starting point,
    so nobody gets a pile of old notes."""
    if not getattr(user, "is_authenticated", False):
        return []
    now = timezone.now()
    marker, created = SeenMarker.objects.get_or_create(user=user, defaults={"seen_at": now})
    if created:
        return []
    notes = list(visible_notes(user).filter(published_at__gt=marker.seen_at)[:10])
    if notes and mark_seen:
        SeenMarker.objects.filter(pk=marker.pk).update(seen_at=now)
    return notes


def mark_seen(user):
    SeenMarker.objects.update_or_create(user=user, defaults={"seen_at": timezone.now()})


def drafts_waiting(user):
    if not is_staff_user(user) or not user.is_superuser:
        return 0
    return ReleaseNote.objects.filter(status=ReleaseNote.DRAFT).count()
