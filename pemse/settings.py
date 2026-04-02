"""
Panhandle EMS Education — Django Settings
Railway (hosting) + AWS S3 (file storage) + PostgreSQL
"""

import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# ── SECURITY ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = ['*']  # Temporary: open while diagnosing Railway healthcheck — lock down after deploy confirms working

RAILWAY_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
if os.environ.get('RAILWAY_PROJECT_ID'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CSRF_TRUSTED_ORIGINS = [
    'https://pemse-production.up.railway.app',
    'https://*.up.railway.app',
]
if RAILWAY_DOMAIN and f'https://{RAILWAY_DOMAIN}' not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RAILWAY_DOMAIN}')
extra = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if extra:
    CSRF_TRUSTED_ORIGINS += [x.strip() for x in extra.split(',')]

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

# ── AUTH ──────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'students.Student'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

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
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── MEDIA / FILE UPLOADS — AWS S3 ────────────────────────────────────────────
AWS_ACCESS_KEY_ID     = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'pemse-documents')
AWS_S3_REGION_NAME    = os.environ.get('AWS_S3_REGION_NAME', 'us-east-2')
AWS_S3_CUSTOM_DOMAIN  = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
AWS_DEFAULT_ACL       = 'private'
AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
AWS_QUERYSTRING_AUTH  = True   # signed URLs — students can only see their own files
AWS_QUERYSTRING_EXPIRE = 300   # URL expires in 5 minutes

if AWS_ACCESS_KEY_ID:
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'
else:
    # Local dev fallback
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

# Max upload size: 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# ── EMAIL ─────────────────────────────────────────────────────────────────────
if os.environ.get('EMAIL_HOST_PASSWORD'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST     = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT     = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS  = True
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL  = 'PEMSE Student Portal <ems.edu911@gmail.com>'
ADMIN_EMAIL = 'ems.edu911@gmail.com'

# ── MISC ──────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Chicago'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'
