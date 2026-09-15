import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import connection
from django.utils import timezone

from laboratorio.models import TestExecution


EXECUTION_TIMEOUT_SECONDS = 30


def execute_cases(owner, candidate, scenario, cases, timeout=EXECUTION_TIMEOUT_SECONDS):
    run_id = f"RUN-{uuid4().hex}"
    revisions = {case.identifier: case.revision for case in cases}
    mandatory_ids = set(owner.test_cases.filter(mandatory=True).values_list("identifier", flat=True))
    selected_ids = {case.identifier for case in cases}
    execution = TestExecution.objects.create(
        run_id=run_id,
        owner=owner,
        candidate=candidate,
        scenario=scenario,
        scenario_revision=scenario.revision,
        code_revision=settings.LAB_REVISION,
        case_revisions=revisions,
        status=TestExecution.WAITING,
        scope_kind="full" if mandatory_ids and mandatory_ids.issubset(selected_ids) else "selection",
    )
    artifact_dir = Path(settings.LAB_EXECUTION_DIR) / run_id
    artifact_dir.mkdir(parents=True, exist_ok=False)
    try:
        execution.artifact_dir = str(artifact_dir.relative_to(settings.BASE_DIR))
    except ValueError:
        execution.artifact_dir = str(artifact_dir)
    execution.status = TestExecution.RUNNING
    execution.started_at = timezone.now()
    execution.save(update_fields=["artifact_dir", "status", "started_at"])

    input_path = artifact_dir / "input.json"
    output_path = artifact_dir / "output.json"
    coverage_data = artifact_dir / ".coverage"
    coverage_json = artifact_dir / "coverage.json"
    temporary_db = artifact_dir / "execution.sqlite3"
    payload = {
        "scenario": {"code": scenario.code, "bug_ids": scenario.bug_ids},
        "cases": [
            {
                "identifier": case.identifier,
                "requirement_id": case.requirement_id,
                "operation": case.operation,
                "inputs": case.inputs,
                "expected": case.expected,
                "revision": case.revision,
            }
            for case in cases
        ],
    }
    input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    env = os.environ.copy()
    env.update({
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "LAB_DB_PATH": str(temporary_db),
        "LAB_EXECUTION_DIR": str(artifact_dir),
    })
    command = [
        sys.executable,
        "-m",
        "coverage",
        "run",
        f"--data-file={coverage_data}",
        "--source=loja.domain,loja.services",
        "manage.py",
        "run_lab_cases",
        str(input_path),
        str(output_path),
    ]
    try:
        connection.close()
        completed = subprocess.run(
            command,
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
        (artifact_dir / "stdout.txt").write_text(completed.stdout[-20000:], encoding="utf-8")
        (artifact_dir / "stderr.txt").write_text(completed.stderr[-20000:], encoding="utf-8")
        if completed.returncode != 0 or not output_path.exists():
            raise RuntimeError(f"Executor terminou com codigo {completed.returncode}: {completed.stderr[-1000:]}")
        coverage_command = [
            sys.executable,
            "-m",
            "coverage",
            "json",
            f"--data-file={coverage_data}",
            "-o",
            str(coverage_json),
        ]
        coverage_result = subprocess.run(coverage_command, cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, timeout=10, shell=False, check=False)
        if coverage_result.returncode != 0:
            raise RuntimeError(f"Falha ao gerar cobertura JSON: {coverage_result.stderr[-1000:]}")
        html_command = [sys.executable, "-m", "coverage", "html", f"--data-file={coverage_data}", "-d", str(artifact_dir / "coverage_html")]
        subprocess.run(html_command, cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, timeout=10, shell=False, check=False)
        result_payload = json.loads(output_path.read_text(encoding="utf-8"))
        coverage_payload = json.loads(coverage_json.read_text(encoding="utf-8"))
        totals = coverage_payload["totals"]
        execution.results = result_payload["results"]
        execution.coverage_lines = int(totals["covered_lines"])
        execution.coverage_considered = int(totals["num_statements"])
        execution.coverage_percent = float(totals["percent_covered"])
        execution.status = TestExecution.COMPLETED
    except subprocess.TimeoutExpired:
        execution.status = TestExecution.ERROR
        execution.error_message = f"Tempo limite de {timeout} segundos excedido. Nenhum caso foi classificado como aprovado ou reprovado."
    except Exception as exc:
        execution.status = TestExecution.ERROR
        execution.error_message = str(exc)
    finally:
        execution.finished_at = timezone.now()
        execution.save(update_fields=["status", "results", "coverage_lines", "coverage_considered", "coverage_percent", "error_message", "finished_at"])
        connection.close()
        for suffix in ("", "-shm", "-wal", "-journal"):
            db_piece = Path(f"{temporary_db}{suffix}")
            if db_piece.exists():
                db_piece.unlink()
    return execution
