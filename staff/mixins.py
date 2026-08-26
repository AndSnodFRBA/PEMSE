from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def staff_required(view_func):
    """Decorator for function-based staff views."""
    @wraps(view_func)
    @login_required(login_url='/staff/login/')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_office_staff:
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """Decorator for program-director-only views (Administrator role or superuser).
    Stricter than staff_required — regular Office Staff accounts are redirected."""
    @wraps(view_func)
    @login_required(login_url='/staff/login/')
    def wrapper(request, *args, **kwargs):
        if not (request.user.role == 'admin' or request.user.is_superuser):
            return redirect('staff_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
