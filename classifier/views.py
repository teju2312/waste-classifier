"""
classifier/views.py

OOP Concepts used here:
- Class-Based Views  : HomeView, PredictView, HistoryView inherit from Django's View/ListView
- Inheritance        : Each view inherits from a Django base view class
- Encapsulation      : Each view class handles only its own responsibility
- Polymorphism       : get() and post() methods behave differently per view class
- Single Responsibility: HomeView = show form, PredictView = run prediction, HistoryView = show logs
"""

import logging
import base64  # CRITICAL: Required to transform the image into an inline data string
from PIL import Image

from django.views         import View
from django.views.generic import ListView
from django.shortcuts     import render, redirect
from django.contrib       import messages
from django.http          import JsonResponse

from .forms    import ImageUploadForm
from .models   import PredictionLog
from .ml_model import WasteClassifier

logger = logging.getLogger(__name__)


class HomeView(View):
    """
    OOP: Inheritance — inherits from Django's View base class.
    OOP: Single Responsibility — only shows the upload form.
    OOP: Polymorphism — get() and post() are different behaviours of the same class.
    """

    template_name = 'classifier/home.html'

    def get(self, request):
        form = ImageUploadForm()
        context = {
            'form': form,
            'total_predictions': PredictionLog.objects.count(),
            'organic_count': PredictionLog.objects.filter(is_organic=True).count(),
            'recyclable_count': PredictionLog.objects.filter(is_organic=False).count(),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        """Handle form submission — redirect to prediction."""
        return redirect('predict')


class PredictView(View):
    """
    OOP: Inheritance — inherits from Django's View.
    OOP: Encapsulation — prediction pipeline (validate → predict → save → render) is self-contained.
    OOP: Abstraction   — calls WasteClassifier().predict() without knowing TF internals.
    """

    template_name = 'classifier/result.html'

    def _get_client_ip(self, request) -> str:
        """
        OOP: Private method — encapsulates IP extraction logic.
        Not exposed outside this class.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def get(self, request):
        """Show upload form on GET request."""
        form = ImageUploadForm()
        return render(request, 'classifier/home.html', {'form': form})

    def post(self, request):
        """
        Handle image upload and run prediction.
        OOP: Encapsulation — all steps kept inside this method.
        """
        form = ImageUploadForm(request.POST, request.FILES)

        if not form.is_valid():
            return render(request, 'classifier/home.html', {'form': form})

        uploaded_file = form.cleaned_data['image']

        try:
            # Open image for prediction
            image = Image.open(uploaded_file)

            # OOP: Abstraction — classifier hides all TF/numpy details
            classifier = WasteClassifier()
            result     = classifier.predict(image)

            # If image is not waste — show rejection page
            if result.get('is_rejected'):
                return render(request, 'classifier/rejected.html', {
                    'form': ImageUploadForm()
                })

            # Reset file pointer before saving to DB
            uploaded_file.seek(0)

            # Save prediction log to Cloud DB
            log = PredictionLog.objects.create(
                image      = uploaded_file,
                label      = result['label'],
                raw_score  = result['raw_score'],
                is_organic = result['is_organic'],
                ip_address = self._get_client_ip(request),
            )

            # ─── SECURE PREVIEW ENGINE LOGIC ────────────────────────────────
            # Extract raw image bytes directly from memory cache prior to closing request
            uploaded_file.seek(0)
            encoded_string = base64.b64encode(uploaded_file.read()).decode('utf-8')
            
            # Determine correct mime type matching the upload extension
            file_extension = uploaded_file.name.split('.')[-1].lower()
            if file_extension not in ['jpeg', 'jpg', 'png', 'webp']:
                file_extension = 'jpeg'  # Standard fallback
            if file_extension == 'jpg':
                file_extension = 'jpeg'

            inline_image_uri = f"data:image/{file_extension};base64,{encoded_string}"
            # ───────────────────────────────────────────────────────────────

            context = {
                'result': result,
                'log':    log,
                'preview_image': inline_image_uri,  # Injected directly to bypass GCS permissions
                'form':   ImageUploadForm(),
            }
            return render(request, self.template_name, context)

        except RuntimeError as e:
            logger.error(f"Model error: {e}")
            messages.error(request, "Model is not available. Please contact admin.")
            return redirect('home')

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            messages.error(request, "Something went wrong. Please try again.")
            return redirect('home')


class HistoryView(ListView):
    """
    OOP: Inheritance — inherits from Django's ListView (generic class-based view).
    OOP: Encapsulation — pagination and queryset logic is self-contained.
    Django's ListView automatically handles pagination and queryset rendering.
    """

    model               = PredictionLog
    template_name       = 'classifier/history.html'
    context_object_name = 'logs'
    paginate_by         = 10

    def get_queryset(self):
        """Return all logs ordered by newest first."""
        return PredictionLog.objects.all().order_by('-created_at')

    def get_context_data(self, **kwargs):
        """
        OOP: Polymorphism — overrides parent's get_context_data to add stats.
        """
        context = super().get_context_data(**kwargs)
        context['total_predictions'] = PredictionLog.objects.count()
        context['organic_count']     = PredictionLog.objects.filter(is_organic=True).count()
        context['recyclable_count']  = PredictionLog.objects.filter(is_organic=False).count()
        return context


class PredictAPIView(View):
    """
    OOP: Inheritance — inherits from View.
    REST API endpoint that returns JSON — for future mobile/GCP integration.
    OOP: Single Responsibility — only handles API responses, not HTML rendering.
    """

    def post(self, request):
        form = ImageUploadForm(request.POST, request.FILES)

        if not form.is_valid():
            return JsonResponse({'error': form.errors}, status=400)

        try:
            image      = Image.open(form.cleaned_data['image'])
            classifier = WasteClassifier()
            result     = classifier.predict(image)
            return JsonResponse({'success': True, 'result': result})

        except Exception as e:
            logger.error(f"API prediction error: {e}")
            return JsonResponse({'error': str(e)}, status=500)