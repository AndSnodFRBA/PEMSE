from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .services import mark_seen, visible_notes


@login_required
def note_list(request):
    notes = visible_notes(request.user)[:100]
    mark_seen(request.user)
    # WHATSNEW_BASE_TEMPLATE: the app's layout (with a {% block content %}) to show the page in.
    # It can be a callable taking the request, for apps with a different layout per role.
    base = getattr(settings, "WHATSNEW_BASE_TEMPLATE", "")
    if callable(base):
        base = base(request)
    template = "whatsnew/list_in_base.html" if base else "whatsnew/list_standalone.html"
    return render(request, template, {"notes": notes, "base_template": base})


@login_required
@require_POST
def seen(request):
    mark_seen(request.user)
    return HttpResponse(status=204)
