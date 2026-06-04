from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    organization = models.CharField(max_length=100, blank=True, null=True)
    role = models.CharField(max_length=100, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Create or update the user profile when User object changes"""
    if created:
        UserProfile.objects.create(user=instance)
    else:
        instance.profile.save()

class DatabaseConnection(models.Model):
    """Model to store user's database connection information"""
    DATABASE_TYPES = [
        ('postgresql', 'PostgreSQL'),
        ('mysql', 'MySQL'),
        ('sqlserver', 'SQL Server'),
        ('oracle', 'Oracle'),
        ('sqlite', 'SQLite'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="database_connections")
    name = models.CharField(max_length=100, help_text="A name to identify this connection")
    database_type = models.CharField(max_length=20, choices=DATABASE_TYPES)
    host = models.CharField(max_length=255, blank=True, null=True, help_text="Database server address")
    port = models.CharField(max_length=10, blank=True, null=True)
    database_name = models.CharField(max_length=100, help_text="Name of the database")
    username = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    connection_string = models.TextField(blank=True, null=True, help_text="Optional full connection string")
    
    # Additional fields for connection options
    ssl_enabled = models.BooleanField(default=False, help_text="Use SSL/TLS for connection")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.name} ({self.database_type})"
    
    class Meta:
        verbose_name = "Database Connection"
        verbose_name_plural = "Database Connections"
