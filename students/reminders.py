"""Pluggable reminder rules for the daily `send_reminders` management command
and the staff bulk-send screen (which reuses these same candidate queries so
the two paths can never drift apart).

Adding a new reminder type = one new ReminderRule subclass + one line in
REMINDER_RULES. Nothing else in the codebase needs to change.
"""
from datetime import timedelta

from .balance import compute_balance
from .emails import (
    _send,
    balance_due_reminder_content,
    course_start_reminder_content,
    registration_incomplete_reminder_content,
)
from .models import ReminderLog, Student


def _active_students():
    return Student.objects.filter(role=Student.Role.STUDENT).exclude(
        enroll_status=Student.EnrollStatus.WITHDRAWN
    )


class ReminderRule:
    key           = None   # unique slug, matches ReminderLog.rule_key
    label         = None   # human-readable, for staff UI
    cooldown_days = None   # int = resend after N days; None = once-ever

    def candidates(self, today):
        """Yield (student, context_dict) for everyone potentially due — ignores cooldown."""
        raise NotImplementedError

    def render(self, student, context):
        """Return (subject, body)."""
        raise NotImplementedError


class RegistrationIncompleteRule(ReminderRule):
    key           = 'registration_incomplete'
    label         = 'Registration incomplete'
    cooldown_days = 7
    grace_days    = 3

    def candidates(self, today):
        cutoff = today - timedelta(days=self.grace_days)
        for student in _active_students():
            if not student.enrollment_complete and student.date_joined.date() <= cutoff:
                yield student, {}

    def render(self, student, context):
        return registration_incomplete_reminder_content(student)


class BalanceDueRule(ReminderRule):
    key           = 'balance_due'
    label         = 'Balance due'
    cooldown_days = 10

    def candidates(self, today):
        for student in _active_students():
            enrollment, _total_paid, _total_owed, balance_due = compute_balance(student)
            if balance_due > 0:
                yield student, {'course': enrollment.course if enrollment else None, 'balance_due': balance_due}

    def render(self, student, context):
        return balance_due_reminder_content(student, context['balance_due'])


class CourseStartApproachingRule(ReminderRule):
    cooldown_days = None  # once-ever per checkpoint

    def __init__(self, days_before):
        self.days_before = days_before
        self.key   = f'course_start_{days_before}'
        self.label = f'Course starts in {days_before} day{"s" if days_before != 1 else ""}'

    def candidates(self, today):
        target = today + timedelta(days=self.days_before)
        for student in _active_students():
            enrollment = getattr(student, 'enrollment', None)
            if enrollment and enrollment.course.start_date == target:
                yield student, {'course': enrollment.course}

    def render(self, student, context):
        return course_start_reminder_content(student, context['course'], self.days_before)


REMINDER_RULES = [
    RegistrationIncompleteRule(),
    BalanceDueRule(),
    *(CourseStartApproachingRule(d) for d in (14, 7, 1)),
]


def run_rule(rule, today, dry_run=False):
    sent = 0
    for student, ctx in rule.candidates(today):
        last = ReminderLog.objects.filter(student=student, rule_key=rule.key).order_by('-sent_at').first()
        if last and (rule.cooldown_days is None or (today - last.sent_at.date()).days < rule.cooldown_days):
            continue
        subject, body = rule.render(student, ctx)
        if not dry_run:
            _send(subject, body, student.email)
            ReminderLog.objects.create(
                student=student, rule_key=rule.key, channel=ReminderLog.Channel.AUTO,
                course=ctx.get('course'), subject=subject, body=body,
            )
        sent += 1
    return sent
