from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Populate the database with demo companies and profiles for the showcase."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING("seed_demo_data is a stub - no data written yet.")
        )
