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
    from .models import SiteSettings

    site = SiteSettings.get()
    return {
        # Name/address/phone/email/director are staff-editable (Staff > Settings >
        # Site Settings) and stored in SiteSettings — everything else (short name,
        # tagline, theme colors, logo) is still env-var-driven branding/theme,
        # not contact info, and has no editable field yet.
        'AGENCY_NAME':       site.agency_name,
        'AGENCY_SHORT_NAME': settings.AGENCY_SHORT_NAME,
        'AGENCY_ADDRESS':    site.agency_address,
        'AGENCY_PHONE':      site.agency_phone,
        'AGENCY_EMAIL':      site.agency_email,
        'AGENCY_DIRECTOR':   site.agency_director,
        'AGENCY_TAGLINE':    settings.AGENCY_TAGLINE,
        'AGENCY_NAVY':       settings.AGENCY_NAVY,
        'AGENCY_ACCENT':     settings.AGENCY_ACCENT,
        'AGENCY_LOGO_URL':   settings.AGENCY_LOGO_URL,
        'DEMO_MODE':         settings.DEMO_MODE,
        'SOFTWARE_COMPANY':     settings.SOFTWARE_COMPANY,
        'SOFTWARE_COMPANY_URL': settings.SOFTWARE_COMPANY_URL,
        'SOFTWARE_VERSION':     settings.SOFTWARE_VERSION,
    }
