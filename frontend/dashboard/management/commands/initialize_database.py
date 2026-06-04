from django.core.management.base import BaseCommand
from django.db import connection, DatabaseError
from django.core.management import call_command
from django.contrib.auth.models import User
import uuid
import os
import sys

class Command(BaseCommand):
    help = 'Initialize database by running migrations and creating initial data'

    def handle(self, *args, **options):
        self.stdout.write('Starting database initialization...')

        # First, apply all migrations
        self.stdout.write(self.style.WARNING('Applying all migrations first...'))
        try:
            call_command('migrate', interactive=False)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during migrations: {str(e)}'))
            return

        # Ensure dashboard_project table exists
        if not self.table_exists('dashboard_project'):
            self.stdout.write(self.style.ERROR('After migrations, dashboard_project table still does not exist'))
            self.stdout.write(self.style.ERROR('Please check your migrations and try again'))
            return

        # Only after migrations are applied, try to create default project
        self.create_default_project()

    def table_exists(self, table_name):
        """Check if a table exists in the database"""
        try:
            with connection.cursor() as cursor:
                # For SQLite
                if connection.vendor == 'sqlite':
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=%s", [table_name])
                    return cursor.fetchone() is not None
                # For PostgreSQL
                elif connection.vendor == 'postgresql':
                    cursor.execute("SELECT to_regclass(%s)", [table_name])
                    return cursor.fetchone()[0] is not None
                # For other databases
                else:
                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_name = %s
                    """, [table_name])
                    return cursor.fetchone()[0] > 0
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error checking if table exists: {str(e)}"))
            return False

    def create_default_project(self):
        """Create a default project after ensuring the table exists"""
        try:
            self.stdout.write('Creating default project...')
            
            # Need to import here after migrations to avoid circular imports or model import errors
            from dashboard.models import Project
            
            # Check if default project already exists
            default_project_id = uuid.UUID('00000000-0000-0000-0000-000000000001')
            if Project.objects.filter(id=default_project_id).exists():
                self.stdout.write(self.style.SUCCESS('Default project already exists.'))
                return
            
            # Get or create admin user
            admin_user = None
            try:
                admin_user = User.objects.filter(is_superuser=True).first()
                if not admin_user:
                    admin_user = User.objects.first()
                if not admin_user:
                    self.stdout.write('Creating admin user...')
                    admin_user = User.objects.create_superuser(
                        username='admin',
                        email='admin@example.com',
                        password='admin123'  # This should be changed immediately in production!
                    )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creating admin user: {str(e)}'))
                return
            
            # Create default project
            Project.objects.create(
                id=default_project_id,
                name='Default Project',
                description='This project was automatically created to store existing datasets.',
                owner=admin_user
            )
            self.stdout.write(self.style.SUCCESS('Default project created successfully!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating default project: {str(e)}'))
            self.stdout.write(self.style.WARNING('You may need to run migrations first: python manage.py migrate'))
