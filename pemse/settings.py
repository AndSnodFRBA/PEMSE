"""
Panhandle EMS Education — Django Settings
Railway (hosting) + AWS S3 (file storage) + PostgreSQL
"""

import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Railway injects real environment variables directly, so this is a no-op in
# production; locally it's what makes .env actually reach os.environ.
load_dotenv(BASE_DIR / '.env')

# ── SECURITY ──────────────────────────────────────────────────────────────────
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
BETA_MODE = os.environ.get('BETA_MODE', 'True') == 'True'

# ── ERROR TRACKING — Sentry ──────────────────────────────────────────────────
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN and not DEBUG:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment='production',
    )

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-local-dev-only-change-me'
    else:
        raise ImproperlyConfigured('SECRET_KEY environment variable must be set in production')

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

CSRF_TRUSTED_ORIGINS = [
    f'https://{host}' for host in ALLOWED_HOSTS
    if host not in ('localhost', '127.0.0.1')
] + ['http://localhost:8000', 'http://127.0.0.1:8000']

# Railway's healthcheck hits the container over its private network using this
# hostname, which isn't a public domain so it's never in ALLOWED_HOSTS above.
RAILWAY_PRIVATE_DOMAIN = os.environ.get('RAILWAY_PRIVATE_DOMAIN')
if RAILWAY_PRIVATE_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PRIVATE_DOMAIN)

if os.environ.get('RAILWAY_PROJECT_ID'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    # Railway's healthcheck hits the container directly over plain HTTP
    # (not through the public HTTPS edge), so /health/ must stay exempt
    # or every deploy's healthcheck fails on the redirect and never goes live.
    SECURE_REDIRECT_EXEMPT = [r'^health/$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ── AUTHENTICATION ────────────────────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    'students.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# ── APPS ──────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'storages',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_extensions',
    # PEMSE apps
    'students',
    'courses',
    'documents',
    'handbook',
    'staff',
    'evaluations',
    'instructor',
    'schedule',
    'grades',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # static files on Railway
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'pemse.middleware.SessionTimeoutWarningMiddleware',
]

ROOT_URLCONF = 'pemse.urls'
WSGI_APPLICATION = 'pemse.wsgi.application'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'evaluations.context_processors.eval_counts',
            'students.context_processors.notifications',
            'pemse.context_processors.site_settings',
        ],
    },
}]

# ── DATABASE — PostgreSQL on Railway ─────────────────────────────────────────
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
        conn_max_age=600,
        ssl_require=not DEBUG and bool(os.environ.get('DATABASE_URL')),
    )
}
DATABASES['default']['CONN_HEALTH_CHECKS'] = True

# ── AUTH ──────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'students.Student'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

# ── Session timeout — 2 hours of inactivity ──────────────────────────────────
SESSION_COOKIE_AGE = 7200        # 2 hours in seconds
SESSION_SAVE_EVERY_REQUEST = True # Reset timer on every request
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Persist across browser restarts

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── STATIC FILES — WhiteNoise on Railway ─────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# ── MEDIA / FILE UPLOADS — AWS S3 ────────────────────────────────────────────
AWS_ACCESS_KEY_ID       = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY   = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'pemse-documents')
AWS_S3_REGION_NAME      = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
AWS_DEFAULT_ACL         = 'private'
AWS_S3_FILE_OVERWRITE   = False
AWS_QUERYSTRING_AUTH    = True   # signed URLs — students can only see their own files
AWS_QUERYSTRING_EXPIRE  = 300    # URL expires in 5 minutes
AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}

if AWS_ACCESS_KEY_ID:
    DEFAULT_FILE_STORAGE_BACKEND = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/'
else:
    DEFAULT_FILE_STORAGE_BACKEND = 'django.core.files.storage.FileSystemStorage'
    MEDIA_URL  = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

# Django 5.1 removed DEFAULT_FILE_STORAGE / STATICFILES_STORAGE in favor of
# this single STORAGES mapping — both prior settings are silently ignored.
STORAGES = {
    'default': {
        'BACKEND': DEFAULT_FILE_STORAGE_BACKEND,
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Max upload size: 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# ── EMAIL — Gmail SMTP ────────────────────────────────────────────────────────
EMAIL_BACKEND      = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST         = 'smtp.gmail.com'
EMAIL_PORT         = 587
EMAIL_USE_TLS      = True
EMAIL_HOST_USER    = os.environ.get('EMAIL_HOST_USER', 'emseducation19@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = 'PEMSE Student Portal <emseducation19@gmail.com>'
ADMIN_EMAIL        = 'emseducation19@gmail.com'

# ── MISC ──────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Chicago'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'
