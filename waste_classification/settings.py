"""
Django settings for waste_classification project.
Sensitive values loaded from environment variables directly in production.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security & Core Environment Variables ─────────────────────────────────────
# Read directly from environment variables injected by Cloud Run
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-production-fallback-key-99709')
DEBUG      = os.getenv('DJANGO_DEBUG', 'False') == 'True'

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

# ── Database — PostgreSQL (DIRECT ENV WITH PROXY SOСКЕТ) ──────────────────────
DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     os.getenv('DB_NAME'),
        'USER':     os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'PORT':     os.getenv('DB_PORT', '5432'),
    }
}

# Auto-route socket connections if running inside Google Cloud Run environment
if os.getenv('K_SERVICE'):
    connection_name = os.getenv('CLOUD_SQL_CONNECTION_NAME', 'noted-casing-499709-d9:asia-south1:waste-classifier-db')
    DATABASES['default']['HOST'] = f'/cloudsql/{connection_name}'
else:
    DATABASES['default']['HOST'] = os.getenv('DB_HOST', 'localhost')
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