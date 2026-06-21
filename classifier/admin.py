from django.contrib import admin
from django.utils.html import format_html
from .models import PredictionLog, ModelInfo


@admin.register(PredictionLog)
class PredictionLogAdmin(admin.ModelAdmin):
    list_display = (
        'label',
        'image_preview',
        'created_at',
        'ip_address',
    )

    list_filter = (
        'label',
        'is_organic',
    )

    search_fields = (
        'label',
    )

    readonly_fields = (
        'created_at',
        'ip_address',
        'raw_score',
        'image_preview',
    )

    ordering = ('-created_at',)

    fieldsets = (
        ('Prediction Information', {
            'fields': (
                'label',
                'raw_score',
                'is_organic',
            )
        }),
        ('Uploaded Image', {
            'fields': (
                'image_preview',
                'image',
            )
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'ip_address',
            )
        }),
    )

    def image_preview(self, obj):
        if obj and obj.image:
            return format_html(
                '<a href="{0}" target="_blank">'
                '<img src="{0}" width="100" height="100" '
                'style="object-fit:cover;border-radius:8px;border:1px solid #ddd;" />'
                '</a>',
                obj.secure_image_url
            )
        return "-"

    image_preview.short_description = "Image Preview"


@admin.register(ModelInfo)
class ModelInfoAdmin(admin.ModelAdmin):
    list_display = (
        'version',
        'accuracy',
        'f1_score',
        'is_active',
        'trained_on',
    )

    list_filter = (
        'is_active',
    )

    search_fields = (
        'version',
    )