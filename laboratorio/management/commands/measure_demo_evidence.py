from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from laboratorio.executor import execute_cases
from laboratorio.models import Candidate, TestExecution


class Command(BaseCommand):
    help = "Mede uma vez as evidencias iniciais dos tres candidatos em bancos isolados."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        user = get_user_model().objects.get(username="aluno")
        cases = list(user.test_cases.filter(mandatory=True).order_by("identifier"))
        expected_revisions = {case.identifier: case.revision for case in cases}
        for code in ("CAND-DEFEITOS", "CAND-CORRIGIDO", "CAND-ALTO-RISCO"):
            candidate = Candidate.objects.select_related("scenario").get(code=code)
            existing = TestExecution.objects.filter(
                owner=user,
                candidate=candidate,
                scenario=candidate.scenario,
                scenario_revision=candidate.scenario.revision,
                code_revision=candidate.code_revision,
                status=TestExecution.COMPLETED,
                scope_kind="full",
            ).first()
            if existing and existing.case_revisions == expected_revisions and not options["force"]:
                self.stdout.write(f"{code}: preservando {existing.run_id}.")
                continue
            execution = execute_cases(user, candidate, candidate.scenario, cases)
            if execution.status == TestExecution.ERROR:
                self.stderr.write(self.style.ERROR(f"{code}: {execution.error_message}"))
            else:
                passed = sum(item["outcome"] == "passed" for item in execution.results)
                self.stdout.write(self.style.SUCCESS(f"{code}: {execution.run_id}; {passed}/{len(execution.results)} aprovados; cobertura {execution.coverage_percent:.2f}%."))
