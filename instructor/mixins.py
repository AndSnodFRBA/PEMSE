from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def instructor_required(view_func):
    """Decorator for function-based instructor views."""
    @wraps(view_func)
    @login_required(login_url='/instructor/')
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_instructor or request.user.is_office_staff):
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
