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
                '<a href="{}" target="_blank">View Image</a>',
                obj.image.url
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