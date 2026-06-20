"""
classifier/forms.py

OOP Concepts used here:
- Inheritance   : ImageUploadForm inherits from forms.Form
- Encapsulation : validation logic is encapsulated inside clean_image()
- Abstraction   : views just call form.is_valid() — no file-size logic exposed
"""

from django import forms
from django.conf import settings


class ImageUploadForm(forms.Form):
    """
    OOP: Inheritance — inherits from Django's forms.Form base class.
    Handles image upload and validation.
    Max file size read from settings (which reads from .env) — never hardcoded.
    """

    image = forms.ImageField(
        label='Upload Waste Image',
        help_text='Supported formats: JPG, JPEG, PNG',
        widget=forms.ClearableFileInput(attrs={
            'accept': 'image/jpeg,image/png',
            'class': 'form-control',
        })
    )

    def clean_image(self):
        """
        OOP: Encapsulation — file size validation hidden inside the form class.
        MAX_UPLOAD_SIZE_MB comes from settings → .env — not hardcoded.
        """
        image   = self.cleaned_data.get('image')
        max_mb  = settings.MAX_UPLOAD_SIZE_MB
        max_bytes = max_mb * 1024 * 1024

        if image and image.size > max_bytes:
            raise forms.ValidationError(
                f"Image too large. Maximum allowed size is {max_mb} MB."
            )

        allowed_types = ['image/jpeg', 'image/png']
        if image and image.content_type not in allowed_types:
            raise forms.ValidationError(
                "Invalid file type. Only JPG and PNG are allowed."
            )

        return image
