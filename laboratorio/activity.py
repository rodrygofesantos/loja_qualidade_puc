from laboratorio.gate import evaluation_freshness
from laboratorio.models import (
    DataPreparationRun,
    GateConfig,
    GateEvaluation,
    LabReport,
    TestExecution,
)


STEP_SPECS = [
    ("context", "Escolher candidato e critérios", "laboratorio:scenarios", "2 min"),
    ("data", "Investigar e tratar dados", "laboratorio:data_quality", "5 min"),
    ("risk", "Interpretar risco", "laboratorio:prediction", "4 min"),
    ("tests", "Propor e executar testes", "laboratorio:test_cases", "8 min"),
    ("coverage", "Examinar cobertura", "laboratorio:coverage", "4 min"),
    ("gate", "Consultar Gate e assistente", "laboratorio:gate", "3 min"),
    ("report", "Concluir relatório", "laboratorio:report", "4 min"),
]


def _compatible_executions(owner, state):
    return TestExecution.objects.filter(
        owner=owner,
        candidate=state.candidate,
        scenario=state.scenario,
        scenario_revision=state.scenario.revision,
        code_revision=state.candidate.code_revision,
        status=TestExecution.COMPLETED,
    ).order_by("-created_at", "-pk")


def _test_summary(owner, state):
    mandatory_cases = list(owner.test_cases.filter(mandatory=True).order_by("identifier"))
    current_revisions = {case.identifier: case.revision for case in mandatory_cases}
    latest_results = {}
    executions = list(_compatible_executions(owner, state))

    # Uma execução mais nova prevalece, mas somente para a revisão atual do caso.
    for execution in executions:
        for result in execution.results:
            identifier = result.get("identifier")
            if (
                identifier in current_revisions
                and result.get("revision") == current_revisions[identifier]
                and identifier not in latest_results
            ):
                latest_results[identifier] = result.get("outcome", "not_run")

    passed = sum(outcome == "passed" for outcome in latest_results.values())
    failed = sum(outcome == "failed" for outcome in latest_results.values())
    not_run = len(mandatory_cases) - passed - failed
    full_execution = next(
        (
            run
            for run in executions
            if run.scope_kind == "full"
            and all(
                run.case_revisions.get(identifier) == revision
                for identifier, revision in current_revisions.items()
            )
        ),
        None,
    )
    return {
        "total": len(mandatory_cases),
        "executed": passed + failed,
        "passed": passed,
        "failed": failed,
        "not_run": not_run,
        "full_execution": full_execution,
    }


def _report_state(owner):
    report = LabReport.objects.filter(owner=owner).first()
    if report is None:
        return None, False, False
    required_values = (
        report.context,
        report.data_decision,
        report.priority,
        report.release_decision,
        report.human_checks,
    )
    started = any(value.strip() for value in required_values) or any(report.checklist.values())
    complete = all(value.strip() for value in required_values)
    return report, started, complete


def build_activity_summary(owner, state):
    tests = _test_summary(owner, state)
    full_execution = tests["full_execution"]
    latest_gate = (
        GateEvaluation.objects.filter(owner=owner, candidate=state.candidate)
        .select_related("candidate", "config")
        .order_by("-created_at", "-pk")
        .first()
    )
    gate_current, gate_stale_reasons = evaluation_freshness(owner, state, latest_gate)
    report, report_started, report_complete = _report_state(owner)

    risk_rule_available = False
    if latest_gate and gate_current:
        risk_rule_available = any(
            rule.get("rule") == "Risco predito" and rule.get("status") in {"pass", "fail"}
            for rule in latest_gate.rule_results
        )

    completed = {
        "context": bool(state.candidate_id and state.scenario_id and GateConfig.objects.exists()),
        "data": DataPreparationRun.objects.filter(owner=owner).exists(),
        "risk": bool((report and report.priority.strip()) or risk_rule_available),
        "tests": bool(tests["total"] and tests["not_run"] == 0),
        "coverage": bool(
            full_execution
            and full_execution.coverage_percent is not None
            and full_execution.coverage_considered not in (None, 0)
        ),
        "gate": bool(latest_gate and gate_current),
        "report": report_complete,
    }

    first_incomplete = next((key for key, *_ in STEP_SPECS if not completed[key]), None)
    steps = []
    for index, (key, label, url_name, duration) in enumerate(STEP_SPECS, start=1):
        if completed[key]:
            status, status_label = "complete", "Concluída"
        elif key == first_incomplete:
            status, status_label = "current", "Em andamento"
        else:
            status, status_label = "pending", "Não iniciada"
        steps.append(
            {
                "number": index,
                "key": key,
                "label": label,
                "url_name": url_name,
                "duration": duration,
                "status": status,
                "status_label": status_label,
            }
        )

    completed_count = sum(completed.values())
    next_labels = {
        "context": "Iniciar atividade",
        "data": "Continuar investigação" if completed_count > 1 else "Iniciar atividade",
        "risk": "Interpretar risco",
        "tests": "Executar testes pendentes",
        "coverage": "Examinar cobertura",
        "gate": "Consultar Quality Gate",
        "report": "Concluir relatório",
    }
    next_step = next((step for step in steps if step["key"] == first_incomplete), None)
    next_action = {
        "label": next_labels.get(first_incomplete, "Revisar relatório"),
        "description": (
            "Todas as etapas possuem artefatos verificáveis. Revise sua decisão final."
            if next_step is None
            else f"Próxima etapa: {next_step['label'].lower()}."
        ),
        "url_name": next_step["url_name"] if next_step else "laboratorio:report",
    }

    if latest_gate is None:
        gate_kind, gate_label = "not-evaluated", "Não avaliado"
    elif not gate_current:
        gate_kind, gate_label = "stale", "Avaliação desatualizada"
    elif latest_gate.status == GateEvaluation.APPROVED:
        gate_kind, gate_label = "approved", "Aprovado"
    elif latest_gate.status == GateEvaluation.BLOCKED:
        gate_kind, gate_label = "blocked", "Bloqueado"
    else:
        gate_kind, gate_label = "insufficient", "Evidências insuficientes"

    gate_issues = []
    if latest_gate:
        gate_issues = [
            rule
            for rule in latest_gate.rule_results
            if rule.get("status") in {"fail", "missing"}
        ]

    return {
        "candidate": state.candidate,
        "scenario": state.scenario,
        "scenario_bug_count": len(state.scenario.bug_ids),
        "tests": tests,
        "coverage": full_execution,
        "latest_gate": latest_gate,
        "gate_current": gate_current,
        "gate_stale_reasons": gate_stale_reasons,
        "gate_kind": gate_kind,
        "gate_label": gate_label,
        "gate_issues": gate_issues,
        "report": report,
        "report_started": report_started,
        "steps": steps,
        "completed_count": completed_count,
        "progress_percent": round((completed_count / len(STEP_SPECS)) * 100),
        "activity_status": "Concluída" if completed_count == len(STEP_SPECS) else "Em andamento",
        "next_action": next_action,
    }
