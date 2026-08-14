def notifications(request):
    """Inject unread notification count into every template context (students only)."""
    if not request.user.is_authenticated:
        return {'unread_notifications': 0}
    if getattr(request.user, 'is_office_staff', False) or getattr(request.user, 'is_instructor', False):
        return {'unread_notifications': 0}
    unread_count = request.user.notifications.filter(is_read=False).count()
    return {'unread_notifications': unread_count}


def agency_branding(request):
    from django.conf import settings
    return {
        'AGENCY_NAME':       settings.AGENCY_NAME,
        'AGENCY_SHORT_NAME': settings.AGENCY_SHORT_NAME,
        'AGENCY_ADDRESS':    settings.AGENCY_ADDRESS,
        'AGENCY_PHONE':      settings.AGENCY_PHONE,
        'AGENCY_EMAIL':      settings.AGENCY_EMAIL,
        'AGENCY_DIRECTOR':   settings.AGENCY_DIRECTOR,
        'AGENCY_TAGLINE':    settings.AGENCY_TAGLINE,
        'AGENCY_NAVY':       settings.AGENCY_NAVY,
        'AGENCY_ACCENT':     settings.AGENCY_ACCENT,
        'AGENCY_LOGO_URL':   settings.AGENCY_LOGO_URL,
        'DEMO_MODE':         settings.DEMO_MODE,
        'SOFTWARE_COMPANY':     settings.SOFTWARE_COMPANY,
        'SOFTWARE_COMPANY_URL': settings.SOFTWARE_COMPANY_URL,
        'SOFTWARE_VERSION':     settings.SOFTWARE_VERSION,
    }
