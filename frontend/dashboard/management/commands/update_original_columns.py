from django.core.management.base import BaseCommand
from dashboard.models import Dataset

class Command(BaseCommand):
    help = 'Atualiza datasets existentes com colunas originais'

    def handle(self, *args, **options):
        updated_count = 0
        for dataset in Dataset.objects.filter(original_columns=[]):
            dataset.original_columns = dataset.columns
            dataset.save()
            updated_count += 1
            self.stdout.write(f"Updated dataset {dataset.upload_id}")
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated_count} datasets')
        )
