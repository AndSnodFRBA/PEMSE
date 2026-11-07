from django import forms
from django.contrib import admin, messages
from django.utils import timezone

from .audiences import AUDIENCES
from .models import ReleaseNote


class ReleaseNoteForm(forms.ModelForm):
    audience = forms.ChoiceField(choices=AUDIENCES, initial="all")

    class Meta:
        model = ReleaseNote
        fields = ["title", "body", "audience", "status"]


@admin.register(ReleaseNote)
class ReleaseNoteAdmin(admin.ModelAdmin):
    form = ReleaseNoteForm
    list_display = ["title", "status", "audience_label", "published_at", "source", "created_at"]
    list_filter = ["status", "audience", "source"]
    search_fields = ["title", "body", "commit_text"]
    readonly_fields = ["published_at", "source", "commit_sha", "commit_text", "created_at"]
    actions = ["publish", "hide"]
    fieldsets = [
        (None, {"fields": ["title", "body", "audience", "status"],
                "description": "Drafts are never shown to users. Edit the wording, pick who should see it, "
                               "then set Status to Published (or use the Publish action on the list)."}),
        ("Where this came from", {"fields": ["source", "commit_sha", "commit_text", "created_at", "published_at"],
                                   "classes": ["collapse"]}),
    ]

    @admin.display(description="Audience")
    def audience_label(self, obj):
        return dict(AUDIENCES).get(obj.audience, obj.audience)

    @admin.action(description="Publish selected notes (users see them on their next visit)")
    def publish(self, request, queryset):
        count = 0
        for note in queryset.exclude(status=ReleaseNote.PUBLISHED):
            note.status = ReleaseNote.PUBLISHED
            note.published_at = timezone.now()
            note.save()
            count += 1
        self.message_user(request, f"Published {count} note(s).", messages.SUCCESS)

    @admin.action(description="Hide selected notes")
    def hide(self, request, queryset):
        count = queryset.update(status=ReleaseNote.HIDDEN)
        self.message_user(request, f"Hid {count} note(s).", messages.SUCCESS)
