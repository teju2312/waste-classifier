"""
classifier/models.py

OOP Concepts used here:
- Inheritance         : PredictionLog and ContactMessage inherit from django.db.models.Model
- Encapsulation       : __str__ method encapsulates how each object represents itself
- Abstraction         : Django ORM abstracts raw MySQL queries into Python objects
"""

import os
import uuid
import datetime
from django.db import models
from django.conf import settings
from google.cloud import storage # Required to connect securely to GCS


def upload_to(instance, filename):
    """
    OOP: Function used as a callable for upload_to.
    Generates a unique path for each uploaded image using UUID.
    No hardcoded paths — uses MEDIA_ROOT from settings.
    """
    ext      = filename.split('.')[-1]
    new_name = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('uploads', new_name)


class PredictionLog(models.Model):
    """
    OOP: Inheritance — inherits from models.Model (Django's base ORM class).
    Stores every prediction made by the classifier.
    Maps directly to the MySQL table 'classifier_predictionlog'.
    """

    LABEL_CHOICES = [
        ('Organic',    'Organic'),
        ('Recyclable', 'Recyclable'),
        ('Rejected',   'Rejected'),
    ]

    image        = models.ImageField(upload_to=upload_to)
    label        = models.CharField(max_length=20, choices=LABEL_CHOICES)
    raw_score    = models.FloatField()
    is_organic   = models.BooleanField(null=True, blank=True, default=None)
    created_at   = models.DateTimeField(auto_now_add=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering        = ['-created_at']
        verbose_name    = 'Prediction Log'
        verbose_name_plural = 'Prediction Logs'

    def __str__(self):
        """OOP: Encapsulation — controls string representation of the object."""
        return f"{self.label} ({self.raw_score}) — {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def secure_image_url(self):
        """
        OOP: Polymorphism / Encapsulation.
        Generates a secure, temporary signed URL when using Google Cloud Storage,
        or safely falls back to a regular URL string during errors or local development.
        """
        if not self.image:
            return ""
        
        # If running locally (without GCS), just use the default standard path
        if not getattr(settings, 'USE_GCS', False):
            try:
                return self.image.url
            except Exception:
                return ""

        try:
            # Uses Cloud Run's native credentials to securely sign a temporary path
            client = storage.Client()
            bucket = client.bucket(settings.GS_BUCKET_NAME)
            
            # Reconstruct the cloud storage path safely
            blob_path = self.image.name
            blob = bucket.blob(blob_path)

            # Generates a temporary link valid for 15 minutes
            url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(minutes=15),
                method="GET",
            )
            return url
        except Exception as e:
            # CRITICAL SAFETY FALLBACK: Log the error to your Cloud Logs, 
            # but return the standard URL string so the page NEVER crashes.
            print(f"Error generating secure signed URL: {e}")
            try:
                return self.image.url
            except Exception:
                return ""

class ModelInfo(models.Model):
    """
    OOP: Inheritance — inherits from models.Model.
    Stores metadata about the trained model (version, accuracy, etc.).
    """

    version      = models.CharField(max_length=50)
    accuracy     = models.FloatField(help_text='Test accuracy as percentage')
    precision    = models.FloatField()
    recall       = models.FloatField()
    f1_score     = models.FloatField()
    trained_on   = models.DateField()
    is_active    = models.BooleanField(default=True)
    notes        = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Model Info'

    def __str__(self):
        return f"v{self.version} — Accuracy: {self.accuracy}%"