from django import template
from django.conf import settings

from ..services import drafts_waiting, unread_notes, visible_notes

register = template.Library()


@register.inclusion_tag("whatsnew/_popup.html", takes_context=True)
def whatsnew_popup(context):
    """Shows new notes once, the first time a page loads after they're published."""
    request = context.get("request")
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"notes": [], "drafts": 0}
    # Staff "viewing as" someone else shouldn't use up that person's pop-up.
    real_user = getattr(request, "real_user", user)
    if real_user is not None and real_user.pk != user.pk:
        return {"notes": [], "drafts": 0}
    # Pages like a two-step sign-in code screen, where the pop-up shouldn't count as seen.
    if request.path.startswith(tuple(getattr(settings, "WHATSNEW_SKIP_PATH_PREFIXES", ()))):
        return {"notes": [], "drafts": 0}
    try:
        notes = unread_notes(user, mark_seen=True)
        drafts = drafts_waiting(user)
    except Exception:  # e.g. tables not created yet; never break a page
        return {"notes": [], "drafts": 0}
    return {"notes": notes, "drafts": drafts, "request": request}


@register.simple_tag(takes_context=True)
def whatsnew_has_notes(context):
    request = context.get("request")
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return False
    try:
        return visible_notes(user).exists()
    except Exception:
        return False
