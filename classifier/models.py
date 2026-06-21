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
import logging

from django.db import models
from django.conf import settings
from google.cloud import storage


def upload_to(instance, filename):
    """
    Generates a unique path for uploaded images.
    """
    ext = filename.split('.')[-1]
    new_name = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('uploads', new_name)


class PredictionLog(models.Model):
    """
    Stores every prediction made by the classifier.
    """

    LABEL_CHOICES = [
        ('Organic', 'Organic'),
        ('Recyclable', 'Recyclable'),
        ('Rejected', 'Rejected'),
    ]

    image = models.ImageField(upload_to=upload_to)
    label = models.CharField(max_length=20, choices=LABEL_CHOICES)
    raw_score = models.FloatField()
    is_organic = models.BooleanField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Prediction Log'
        verbose_name_plural = 'Prediction Logs'

    def __str__(self):
        return (
            f"{self.label} ({self.raw_score}) — "
            f"{self.created_at.strftime('%Y-%m-%d %H:%M')}"
        )

    @property
    def secure_image_url(self):
        """
        Generates a signed URL for private GCS objects.

        Local Development:
            Returns standard Django image URL.

        Production (Cloud Run + GCS):
            Returns a temporary signed URL valid for 15 minutes.
        """

        if not self.image:
            return ""

        # Local development
        if not getattr(settings, 'USE_GCS', False):
            try:
                return self.image.url
            except Exception:
                return ""

        try:
            client = storage.Client(
                project=settings.GCP_PROJECT_ID
            )

            bucket = client.bucket(
                settings.GS_BUCKET_NAME
            )

            blob = bucket.blob(
                self.image.name
            )

            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(minutes=15),
                method="GET",
            )

            return signed_url

        except Exception as e:
            logging.exception(
                f"SIGNED URL ERROR for {self.image.name}: {e}"
            )
            return ""


class ModelInfo(models.Model):
    """
    Stores metadata about the trained model.
    """

    version = models.CharField(max_length=50)
    accuracy = models.FloatField(
        help_text='Test accuracy as percentage'
    )
    precision = models.FloatField()
    recall = models.FloatField()
    f1_score = models.FloatField()
    trained_on = models.DateField()
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Model Info'

    def __str__(self):
        return (
            f"v{self.version} — Accuracy: {self.accuracy}%"
        )