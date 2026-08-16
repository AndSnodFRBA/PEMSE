import os

from django.utils import timezone


class RealIPMiddleware:
    """Set REMOTE_ADDR from X-Forwarded-For on Railway.

    Railway's edge is the only proxy in front of this app (same trust
    boundary as SECURE_PROXY_SSL_HEADER below), but without this every
    request reaches Django with REMOTE_ADDR set to the edge's own address
    instead of the visitor's. That collapses every visitor into a single
    IP for anything keyed on request.META['REMOTE_ADDR'] — notably
    django-axes, whose AXES_LOCKOUT_PARAMETERS = ['ip_address'] then locks
    out every visitor together after AXES_FAILURE_LIMIT failed logins from
    anyone, anywhere, rather than just the one visitor responsible.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = bool(os.environ.get('RAILWAY_PROJECT_ID'))

    def __call__(self, request):
        if self.enabled:
            forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if forwarded_for:
                request.META['REMOTE_ADDR'] = forwarded_for.split(',')[0].strip()
        return self.get_response(request)


class SessionTimeoutWarningMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response
