def notifications(request):
    """Inject unread notification count into every template context (students only)."""
    if not request.user.is_authenticated:
        return {'unread_notifications': 0}
    if getattr(request.user, 'is_office_staff', False) or getattr(request.user, 'is_instructor', False):
        return {'unread_notifications': 0}
    unread_count = request.user.notifications.filter(is_read=False).count()
    return {'unread_notifications': unread_count}
