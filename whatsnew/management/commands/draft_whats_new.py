"""Turn this deploy's new commits into one draft What's New note.

Runs automatically after `migrate` on every deploy. Drafts are never shown to users
until the owner reviews and publishes them in the admin.

Commits come from `git log` when the deploy has a .git folder; otherwise from
Railway's RAILWAY_GIT_COMMIT_SHA / RAILWAY_GIT_COMMIT_MESSAGE variables (the latest
commit of the push). Each commit is only ever drafted once.
"""
import os
import re
import subprocess

from django.core.management.base import BaseCommand

from whatsnew.models import ReleaseNote

TRAILER = re.compile(r"^(Co-Authored-By|Claude-Session|Signed-off-by|Reviewed-by|Change-Id):", re.I)
SKIP_SUBJECT = re.compile(r"^(Merge |Revert \"|Trigger redeploy|Bump |chore|ci|test|tests|wip)\b", re.I)


def clean(message):
    lines = [l.rstrip() for l in (message or "").strip().splitlines()]
    lines = [l for l in lines if not TRAILER.match(l.strip()) and not l.strip().startswith("https://claude.ai/")]
    subject = lines[0].strip() if lines else ""
    body = "\n".join(lines[1:]).strip()
    return subject, body


def git(*args):
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


class Command(BaseCommand):
    help = "Create a draft What's New note from this deploy's commits."

    def handle(self, *args, **options):
        head = (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or (git("rev-parse", "HEAD") or "")).strip()
        if not head:
            self.stdout.write("draft_whats_new: no commit information on this deploy, skipping.")
            return
        if ReleaseNote.objects.filter(commit_sha=head).exists():
            self.stdout.write(f"draft_whats_new: commit {head[:7]} already drafted.")
            return

        commits = []  # (sha, subject, body)
        last = ReleaseNote.objects.exclude(commit_sha="").order_by("-created_at").first()
        if last and git("cat-file", "-e", last.commit_sha + "^{commit}") is not None:
            log = git("log", f"{last.commit_sha}..{head}", "--no-merges", "--format=%H%x1f%B%x1e") or ""
            for chunk in log.split("\x1e"):
                if "\x1f" in chunk:
                    sha, message = chunk.strip("\n").split("\x1f", 1)
                    commits.append((sha.strip(), *clean(message)))
        if not commits:
            message = os.environ.get("RAILWAY_GIT_COMMIT_MESSAGE") or git("log", "-1", "--format=%B", head) or ""
            subject, body = clean(message)
            if subject:
                commits = [(head, subject, body)]
        commits = [c for c in commits if c[1] and not SKIP_SUBJECT.match(c[1])]
        if not commits:
            self.stdout.write("draft_whats_new: nothing user-facing in this deploy.")
            return

        commits.reverse() if len(commits) > 1 else None  # git log is newest first; list oldest first
        if len(commits) == 1:
            _, title, body = commits[0]
        else:
            title = f"Updates ({len(commits)} changes)"
            body = "\n".join(f"- {subject}" for _, subject, _ in commits)
        ReleaseNote.objects.create(
            title=title[:200], body=body, status=ReleaseNote.DRAFT, source="auto", commit_sha=head,
            commit_text="\n\n".join(f"{sha[:7]} {subject}\n{body}".strip() for sha, subject, body in commits),
        )
        self.stdout.write(f"draft_whats_new: drafted a note from {len(commits)} commit(s) — review it in the admin.")
