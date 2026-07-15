import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pemse.settings')
django_application = get_wsgi_application()


def application(environ, start_response):
    # Bypass Django entirely for the healthcheck so it can't be rejected by
    # ALLOWED_HOSTS, SECURE_SSL_REDIRECT, or any other request-level middleware
    # regardless of what Host header Railway's internal prober sends.
    if environ.get('PATH_INFO') == '/health/':
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'ok']
    return django_application(environ, start_response)
