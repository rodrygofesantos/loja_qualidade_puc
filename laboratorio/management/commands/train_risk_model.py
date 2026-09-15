from django.core.management.base import BaseCommand

from laboratorio.ml import train_model


class Command(BaseCommand):
    help = "Treina e salva o pipeline temporal de risco."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        metadata = train_model(force=options["force"])
        self.stdout.write(self.style.SUCCESS(f"Modelo {metadata['model_version']} preparado; teste n={metadata['test_metrics']['observations']}."))

