import json
from uuid import uuid4

from django.conf import settings

from laboratorio.ml import load_artifact
from laboratorio.models import GateConfig, GateEvaluation, RiskPrediction, TestExecution
from laboratorio.scenarios import BUGS


def correction_evidence(owner, candidate, bug_id, passing_execution=None):
    expected_requirement = BUGS.get(bug_id, {}).get("requirement")
    if expected_requirement is None:
        return {"verified": False, "bug_id": bug_id, "reason": "Defeito nao existe no catalogo versionado."}
    executions = list(
        TestExecution.objects.filter(owner=owner, status=TestExecution.COMPLETED, code_revision=candidate.code_revision)
        .select_related("scenario", "candidate")
        .order_by("-created_at")
    )
    if passing_execution is not None and passing_execution not in executions:
        executions.insert(0, passing_execution)
    corrected_results = {}
    defective_results = {}
    for execution in executions:
        for result in execution.results:
            identifier = result.get("identifier")
            revision = result.get("revision")
            key = (identifier, revision, result.get("requirement_id"))
            if execution.candidate_id == candidate.pk and not execution.scenario.bug_ids and result.get("outcome") == "passed":
                corrected_results.setdefault(key, {"run_id": execution.run_id, "result": result})
            if bug_id in execution.scenario.bug_ids and result.get("outcome") == "failed":
                defective_results.setdefault(key, {"run_id": execution.run_id, "result": result})
    shared = sorted(
        (
            key
            for key in set(corrected_results).intersection(defective_results)
            if key[2] == expected_requirement
            and corrected_results[key]["result"].get("expected") is not None
            and corrected_results[key]["result"].get("expected") == defective_results[key]["result"].get("expected")
        ),
        key=str,
    )
    if not shared:
        return {"verified": False, "bug_id": bug_id, "reason": "Falta o mesmo caso falhando no defeito e passando no cenario corrigido."}
    key = shared[0]
    return {
        "verified": True,
        "bug_id": bug_id,
        "test_identifier": key[0],
        "case_revision": key[1],
        "requirement_id": key[2],
        "defective_run": defective_results[key]["run_id"],
        "corrected_run": corrected_results[key]["run_id"],
    }


def evaluate_gate(owner, candidate, persist=True):
    config = GateConfig.objects.order_by("-version").first()
    if config is None:
        raise RuntimeError("Configuracao do Gate ausente.")
    mandatory_cases = list(owner.test_cases.filter(mandatory=True).order_by("identifier"))
    execution = (
        TestExecution.objects.filter(
            owner=owner,
            candidate=candidate,
            scenario=candidate.scenario,
            scenario_revision=candidate.scenario.revision,
            code_revision=candidate.code_revision,
            status=TestExecution.COMPLETED,
            scope_kind="full",
        )
        .order_by("-created_at")
        .first()
    )
    result_by_id = {result.get("identifier"): result for result in (execution.results if execution else [])}
    rules = []

    critical = list(candidate.open_critical_defects)
    rules.append({
        "rule": "Defeitos criticos",
        "status": "fail" if critical else "pass",
        "detail": f"Abertos: {', '.join(critical)}" if critical else "Nenhum defeito critico aberto.",
    })

    if not mandatory_cases:
        test_status, test_detail = "missing", "A lista de testes obrigatorios esta vazia; isso nao representa 100%."
    elif not execution:
        test_status, test_detail = "missing", "Nao ha execucao completa compativel com candidato, cenario e revisao."
    else:
        absent = [case.identifier for case in mandatory_cases if case.identifier not in result_by_id]
        stale = [case.identifier for case in mandatory_cases if execution.case_revisions.get(case.identifier) != case.revision]
        failed = [case.identifier for case in mandatory_cases if result_by_id.get(case.identifier, {}).get("outcome") in {"failed", "not_run"}]
        if failed:
            test_status, test_detail = "fail", f"Reprovados ou nao executados: {', '.join(failed)}."
        elif absent or stale:
            test_status, test_detail = "missing", f"Ausentes: {', '.join(absent) or 'nenhum'}; desatualizados: {', '.join(stale) or 'nenhum'}."
        else:
            test_status, test_detail = "pass", f"{len(mandatory_cases)} de {len(mandatory_cases)} obrigatorios aprovados."
    rules.append({"rule": "Testes obrigatorios", "status": test_status, "detail": test_detail})

    if not execution or execution.coverage_considered in (None, 0) or execution.coverage_percent is None:
        coverage_status, coverage_detail = "missing", "Cobertura real ausente ou sem denominador."
    elif execution.coverage_percent < config.coverage_threshold:
        coverage_status, coverage_detail = "fail", f"{execution.coverage_percent:.2f}% < {config.coverage_threshold:.2f}% ({execution.coverage_lines}/{execution.coverage_considered} linhas)."
    else:
        coverage_status, coverage_detail = "pass", f"{execution.coverage_percent:.2f}% >= {config.coverage_threshold:.2f}% ({execution.coverage_lines}/{execution.coverage_considered} linhas)."
    rules.append({"rule": "Cobertura", "status": coverage_status, "detail": coverage_detail})

    if not candidate.declared_fixes:
        fixes_status, fixes_detail, fixes = "na", "Nao aplicavel: o candidato nao declara correcoes.", []
    else:
        fixes = [correction_evidence(owner, candidate, bug_id, execution) for bug_id in candidate.declared_fixes]
        unverified = [item["bug_id"] for item in fixes if not item["verified"]]
        if unverified:
            fixes_status, fixes_detail = "missing", f"Sem comparacao pertinente: {', '.join(unverified)}."
        else:
            fixes_status, fixes_detail = "pass", f"{len(fixes)} correcoes reproduzidas e verificadas com o mesmo caso."
    rules.append({"rule": "Correcoes declaradas", "status": fixes_status, "detail": fixes_detail, "evidence": fixes})

    try:
        _, metadata = load_artifact()
        model_version = metadata["model_version"]
        predictions = list(RiskPrediction.objects.filter(candidate=candidate, model_version=model_version))
        scores = {item.module: item.score for item in predictions}
        missing_modules = [module for module in candidate.changed_modules if module not in scores]
        blocked_modules = [module for module, score in scores.items() if module in candidate.changed_modules and score >= config.risk_threshold]
        if not candidate.changed_modules:
            risk_status, risk_detail = "missing", "Candidato sem modulos alterados nao e atalho para aprovacao."
        elif missing_modules:
            risk_status, risk_detail = "missing", f"Inferencia ausente: {', '.join(missing_modules)}."
        elif blocked_modules:
            risk_status = "fail"
            risk_detail = "; ".join(f"{module}={scores[module]:.6f}" for module in blocked_modules) + f" (limiar {config.risk_threshold:.2f})."
        else:
            risk_status = "pass"
            risk_detail = "; ".join(f"{module}={scores[module]:.6f}" for module in candidate.changed_modules) + f" (< {config.risk_threshold:.2f})."
    except RuntimeError as exc:
        model_version, scores = None, {}
        risk_status, risk_detail = "missing", str(exc)
    rules.append({"rule": "Risco predito", "status": risk_status, "detail": risk_detail})

    integrity_problems = []
    if execution is None:
        integrity_problems.append("execucao completa compativel ausente")
    elif any(result.get("outcome") == "not_run" for result in execution.results):
        integrity_problems.append("caso nao executado")
    if model_version is None:
        integrity_problems.append("modelo indisponivel")
    integrity_status = "missing" if integrity_problems else "pass"
    rules.append({"rule": "Integridade das evidencias", "status": integrity_status, "detail": ", ".join(integrity_problems) if integrity_problems else "Candidato, cenario, revisoes, execucao e modelo compativeis."})

    if any(rule["status"] == "fail" for rule in rules):
        status = GateEvaluation.BLOCKED
    elif any(rule["status"] == "missing" for rule in rules):
        status = GateEvaluation.INSUFFICIENT
    else:
        status = GateEvaluation.APPROVED
    snapshot = {
        "candidate_code": candidate.code,
        "candidate_revision": candidate.code_revision,
        "scenario_code": candidate.scenario.code,
        "scenario_revision": candidate.scenario.revision,
        "execution_run_id": execution.run_id if execution else None,
        "model_version": model_version,
        "risk_scores": scores,
        "config_version": config.version,
        "mandatory_case_revisions": {case.identifier: case.revision for case in mandatory_cases},
    }
    if persist:
        return GateEvaluation.objects.create(
            evaluation_id=f"GATE-{uuid4().hex}",
            owner=owner,
            candidate=candidate,
            config=config,
            status=status,
            rule_results=rules,
            evidence_snapshot=snapshot,
        )
    return {"status": status, "rules": rules, "snapshot": snapshot, "config": config}
