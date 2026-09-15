from django.core.management.base import BaseCommand

from laboratorio.data_pipeline import generate_synthetic_data, prepare_data


class Command(BaseCommand):
    help = "Gera os dados historicos sinteticos e a camada tratada."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        generate_synthetic_data(force=options["force"])
        frame, log = prepare_data(force=False)
        self.stdout.write(self.style.SUCCESS(f"Dados preparados: {len(frame)} observacoes; seed {log['seed']}."))

