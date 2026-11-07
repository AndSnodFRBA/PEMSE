from django.conf import settings
from django.db import models
from django.utils import timezone


class ReleaseNote(models.Model):
    """One "What's New" entry. Drafts are invisible to users until published."""

    DRAFT, PUBLISHED, HIDDEN = "draft", "published", "hidden"
    STATUS_CHOICES = [(DRAFT, "Draft (not shown)"), (PUBLISHED, "Published"), (HIDDEN, "Hidden")]

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, help_text="Plain text. Blank lines start a new paragraph; lines starting with '- ' become bullets.")
    audience = models.CharField(max_length=40, default="all", help_text="Who sees this note.")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=10, default="manual", editable=False)
    commit_sha = models.CharField(max_length=64, blank=True, editable=False, db_index=True)
    commit_text = models.TextField(blank=True, editable=False, help_text="The original commit message(s) this draft came from.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name = "What's New note"
        verbose_name_plural = "What's New notes"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status == self.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def body_blocks(self):
        """Split the body into paragraphs and bullet lists for display."""
        blocks, bullets, para = [], [], []

        def flush():
            if para:
                blocks.append(("p", " ".join(para)))
                para.clear()
            if bullets:
                blocks.append(("ul", list(bullets)))
                bullets.clear()

        for raw in (self.body or "").splitlines():
            line = raw.strip()
            if not line:
                flush()
            elif line.startswith(("- ", "* ", "• ")):
                if para:
                    blocks.append(("p", " ".join(para)))
                    para.clear()
                bullets.append(line[2:].strip())
            else:
                if bullets:
                    blocks.append(("ul", list(bullets)))
                    bullets.clear()
                para.append(line)
        flush()
        return blocks


class SeenMarker(models.Model):
    """When each user last saw What's New. Notes published after this are "new" for them."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="whatsnew_seen")
    seen_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user} saw What's New at {self.seen_at:%Y-%m-%d %H:%M}"
