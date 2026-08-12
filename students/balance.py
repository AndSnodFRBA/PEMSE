"""Shared balance-due calculation for code that needs it across a whole queryset
(reminder rules, staff bulk-send filtering) rather than for a single known student.
"""
from decimal import Decimal

from django.db.models import Sum


def compute_balance(student):
    from courses.models import CourseEnrollment

    enrollment = CourseEnrollment.objects.filter(student=student).select_related('course').first()
    total_paid = student.payment_history.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    late_fees  = student.late_fees.filter(waived=False).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    total_owed = (enrollment.total_tuition if enrollment else Decimal('0')) + late_fees
    balance_due = max(Decimal('0'), total_owed - total_paid)
    return enrollment, total_paid, total_owed, balance_due
