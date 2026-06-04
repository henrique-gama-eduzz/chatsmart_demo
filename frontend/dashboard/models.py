from django.db import models
from django.contrib.auth.models import User
import uuid
import json

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    def get_datasets_count(self):
        return self.datasets.count()
    
    def get_analyses_count(self):
        return Analysis.objects.filter(dataset__project=self).count()
    
    def get_recent_analyses(self, limit=5):
        """Get the most recent analyses for this project"""
        from django.db.models import Q
        return Analysis.objects.filter(
            dataset__project=self
        ).filter(
            Q(status='completed') | Q(status='failed')
        ).order_by('-updated_at')[:limit]

class Dataset(models.Model):
    upload_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="datasets")
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='datasets/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    column_descriptions = models.JSONField(default=dict, blank=True)
    columns = models.JSONField(default=list, blank=True)
    original_columns = models.JSONField(default=list, blank=True)  # Colunas originais do upload
    rows = models.IntegerField(default=0)
    analysis_objective = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.name} ({self.upload_id})"
    
    def get_created_columns(self):
        """Retorna lista de colunas criadas após o upload original"""
        original = set(self.original_columns or [])
        current = set(self.columns or [])
        return list(current - original)
    
    def get_removed_columns(self):
        """Retorna lista de colunas removidas após o upload original"""
        original = set(self.original_columns or [])
        current = set(self.columns or [])
        return list(original - current)

class Analysis(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('running', 'Em execução'),
        ('completed', 'Concluída'),
        ('failed', 'Falhou'),
    ]
    
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='analyses')
    number = models.IntegerField()
    name = models.CharField(max_length=255)
    dependent_vars = models.JSONField(default=list)
    independent_vars = models.JSONField(default=list)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    results = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('dataset', 'number')
        ordering = ['number']
    
    def __str__(self):
        return f"Análise {self.number}: {self.name}"
    
    def get_plots(self):
        if not self.results or not isinstance(self.results, dict):
            return []
        return self.results.get('plots', [])
    
    def get_tables(self):
        if not self.results or not isinstance(self.results, dict):
            return []
        return self.results.get('tables', [])
    
    def get_interpretation(self):
        if not self.results or not isinstance(self.results, dict):
            return ""
        return self.results.get('interpretation', "")
    
    def is_successful(self):
        return self.status == 'completed' and self.results and self.results.get('success', False)
