import json
from pathlib import Path
from types import SimpleNamespace

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from laboratorio.case_adapter import run_one_case


class Command(BaseCommand):
    help = "Executa pacote validado no banco temporario definido por LAB_DB_PATH."

    def add_arguments(self, parser):
        parser.add_argument("input_path")
        parser.add_argument("output_path")

    def handle(self, *args, **options):
        input_path = Path(options["input_path"])
        output_path = Path(options["output_path"])
        if not input_path.is_file():
            raise CommandError("Arquivo de entrada inexistente.")
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        scenario_data = payload.get("scenario", {})
        scenario = SimpleNamespace(code=scenario_data.get("code", "unknown"), bug_ids=list(scenario_data.get("bug_ids", [])))
        call_command("migrate", verbosity=0, interactive=False)
        results = [run_one_case(case, scenario) for case in payload.get("cases", [])]
        output_path.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

