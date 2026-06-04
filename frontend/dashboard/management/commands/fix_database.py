from django.core.management.base import BaseCommand
from django.db import connection
from django.core.management import call_command
from django.contrib.auth.models import User
import uuid

class Command(BaseCommand):
    help = 'Fix database issues by running migrations and creating initial data'

    def handle(self, *args, **options):
        self.stdout.write('Starting database repair...')
        
        # Detect database type
        db_engine = connection.vendor
        self.stdout.write(f'Detected database: {db_engine}')

        # Reset migrations
        self.stdout.write(self.style.WARNING('Applying migrations...'))
        try:
            self.stdout.write('Running migrations...')
            call_command('migrate', interactive=False)
            self.stdout.write(self.style.SUCCESS('Migrations applied successfully!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during migrations: {str(e)}'))
            return

        # Create admin user if none exists
        try:
            if not User.objects.filter(is_superuser=True).exists():
                self.stdout.write('Creating admin user...')
                User.objects.create_superuser(
                    username='admin',
                    email='admin@example.com',
                    password='admin123'  # Should be changed immediately
                )
                self.stdout.write(self.style.SUCCESS('Admin user created successfully!'))
            else:
                self.stdout.write('Admin user already exists.')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating admin user: {str(e)}'))

        # Create default project if needed
        try:
            from dashboard.models import Project
            default_project_id = uuid.UUID('00000000-0000-0000-0000-000000000001')
            
            if not Project.objects.filter(id=default_project_id).exists():
                self.stdout.write('Creating default project...')
                admin_user = User.objects.filter(is_superuser=True).first()
                if admin_user:
                    Project.objects.create(
                        id=default_project_id,
                        name='Default Project',
                        description='This project was automatically created to store existing datasets.',
                        owner=admin_user
                    )
                    self.stdout.write(self.style.SUCCESS('Default project created!'))
                else:
                    self.stdout.write(self.style.ERROR('No admin user found to associate with default project.'))
            else:
                self.stdout.write('Default project already exists.')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating default project: {str(e)}'))
            
        self.stdout.write(self.style.SUCCESS('Database repair complete!'))
