from .models import PreceptorEvaluation


def eval_counts(request):
    """Inject pending evaluation count into every template context."""
    if not request.user.is_authenticated:
        return {}
    if not getattr(request.user, 'is_office_staff', False):
        return {}
    pending = PreceptorEvaluation.objects.filter(
        status=PreceptorEvaluation.Status.PENDING
    ).count()
    return {'eval_pending_count': pending}
