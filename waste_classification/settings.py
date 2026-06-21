"""
Django settings for waste_classification project.
Sensitive values loaded from .env locally, or Google Secret Manager in production.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Secret Manager helper ────────────────────────────────────────────────────
USE_SECRET_MANAGER = os.getenv('USE_SECRET_MANAGER', 'False') == 'True'
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'noted-casing-499709-d9')

_secret_client = None

def get_secret(secret_id, default=None):
    """
    Fetches a secret value from Google Secret Manager if USE_SECRET_MANAGER
    is enabled (set this env var to 'True' only in Cloud Run). Otherwise,
    falls back to reading from .env via os.getenv, so local development is
    affected.
    """
    if not USE_SECRET_MANAGER:
        return os.getenv(secret_id.upper().replace('-', '_'), default)

    global _secret_client
    from google.cloud import secretmanager

    if _secret_client is None:
        _secret_client = secretmanager.SecretManagerServiceClient()

    name = f"projects/{GCP_PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = _secret_client.access_secret_version(name=name)
    return response.payload.data.decode('UTF-8')


# ── Security (UPDATED PRODUCTION FIXES) ───────────────────────────────────────
SECRET_KEY = get_secret('django-secret-key', os.getenv('DJANGO_SECRET_KEY', 'django-insecure-production-fallback-key-99709'))

DEBUG      = os.getenv('DJANGO_DEBUG', 'False') == 'True'

# Read from env if present; otherwise automatically include your Cloud Run live domain
raw_hosts = os.getenv('DJANGO_ALLOWED_HOSTS')
if raw_hosts:
    ALLOWED_HOSTS = raw_hosts.split(',')
else:
    ALLOWED_HOSTS = [
        'localhost', 
        '127.0.0.1', 
        'waste-classifier-service-950820900256.asia-south1.run.app'
    ]

CSRF_TRUSTED_ORIGINS = [
    'https://' + host for host in ALLOWED_HOSTS if host not in ('localhost', '127.0.0.1')
]
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

# ── Installed Apps ────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'classifier',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'waste_classification.urls'

TEMPLATES = [
    {
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
    },
]

WSGI_APPLICATION = 'waste_classification.wsgi.application'

# ── Database — PostgreSQL (BULLETPROOF CLOUD RUN SOCKET ROUTE) ────────────────
DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     get_secret('db-name', os.getenv('DB_NAME')),
        'USER':     get_secret('db-user', os.getenv('DB_USER')),
        'PASSWORD': get_secret('db-password', os.getenv('DB_PASSWORD')),
        'PORT':     get_secret('db-port', os.getenv('DB_PORT', '5432')),
    }
}

# Explicitly detect if we are running in the Google Cloud Run live container
if os.getenv('K_SERVICE') or USE_SECRET_MANAGER:
    # Use the static instance descriptor path that matches your infrastructure configuration
    connection_name = os.getenv('CLOUD_SQL_CONNECTION_NAME', 'noted-casing-499709-d9:asia-south1:waste-classifier-db')
    DATABASES['default']['HOST'] = f'/cloudsql/{connection_name}'
else:
    # Local fallback option
    DATABASES['default']['HOST'] = get_secret('db-host', os.getenv('DB_HOST', 'localhost'))
# ── Password Validation ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Static & Media ────────────────────────────────────────────────────────────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / os.getenv('MEDIA_ROOT', 'media')

# ── Google Cloud Storage (production media files) ────────────────────────────
USE_GCS = os.getenv('USE_GCS', 'False') == 'True'

if USE_GCS:
    GS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME')
    GS_PROJECT_ID = GCP_PROJECT_ID
    GS_DEFAULT_ACL = None  # bucket already has uniform access control + public access prevention
    GS_FILE_OVERWRITE = False
    
    # CRITICAL FIX: Disable querystring auth to prevent private key signing error
    GS_QUERYSTRING_AUTH = False
    
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

    MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/uploads/'
    GS_LOCATION = 'uploads'


# ── ML Model Config (SELF-HEALING CLOUD DEPLOYMENT) ───────────────────────────
MODEL_DIR = BASE_DIR / 'models'
MODEL_DIR.mkdir(exist_ok=True)  # Ensure the directory exists inside the container
# CHANGED HERE: Match the exact bucket filename
MODEL_PATH = MODEL_DIR / 'waste_classifier.keras'

MAX_UPLOAD_SIZE_MB = int(os.getenv('MAX_UPLOAD_SIZE_MB', 10))

# If running in production (USE_GCS is True) and the model file isn't present, stream it from GCS
if os.getenv('USE_GCS', 'False') == 'True' and not MODEL_PATH.exists():
    try:
        print("Production environment: Downloading model file from GCS bucket...")
        from google.cloud import storage
        
        # Pull bucket configuration definitions cleanly
        bucket_name = os.getenv('GCS_BUCKET_NAME', 'waste-classifier-bucket')
        storage_client = storage.Client(project=GCP_PROJECT_ID)
        bucket = storage_client.bucket(bucket_name)
        
        # CHANGED HERE: Match the exact bucket filename
        blob = bucket.blob('waste_classifier.keras')
        blob.download_to_filename(str(MODEL_PATH))
        print("Model file downloaded from GCS successfully!")
    except Exception as e:
        print(f"Warning: Failed to auto-download model from GCS bucket: {e}")
# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Kolkata'
USE_I18N      = True
USE_TZ        = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Logging Configuration (PRODUCTION CRASH LOGGING EXPLICIT) ──────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'ERROR',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}