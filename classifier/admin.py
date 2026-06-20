from django.contrib import admin
from .models import PredictionLog, ModelInfo


@admin.register(PredictionLog)
class PredictionLogAdmin(admin.ModelAdmin):
    list_display  = ('label', 'created_at', 'ip_address')
    list_filter   = ('label', 'is_organic')
    search_fields = ('label',)
    readonly_fields = ('created_at', 'ip_address', 'raw_score')
    ordering = ('-created_at',)


@admin.register(ModelInfo)
class ModelInfoAdmin(admin.ModelAdmin):
    list_display = ('version', 'accuracy', 'f1_score', 'is_active', 'trained_on')
    list_filter  = ('is_active',)
