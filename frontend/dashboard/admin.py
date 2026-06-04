from django.contrib import admin
from .models import Dataset, Analysis

@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ('name', 'upload_id', 'rows', 'uploaded_at')
    search_fields = ('name', 'upload_id')
    readonly_fields = ('upload_id', 'uploaded_at')

@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'dataset', 'status', 'updated_at')
    list_filter = ('status', 'dataset')
    search_fields = ('name', 'content')
    readonly_fields = ('created_at', 'updated_at')
