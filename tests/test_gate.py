from uuid import uuid4

import pytest
from django.test import override_settings

from laboratorio.bot import answer
from laboratorio.gate import correction_evidence, evaluate_gate
from laboratorio.models import Candidate, GateEvaluation, RiskPrediction, TestExecution as ExecutionRecord


def full_execution(user, candidate, coverage=80.0, results=None, stale=False):
    cases = list(user.test_cases.filter(mandatory=True))
    if results is None:
        results = [
            {"identifier": case.identifier, "requirement_id": case.requirement_id, "revision": case.revision, "outcome": "passed", "expected": case.expected, "observed": case.expected, "inputs": case.inputs}
            for case in cases
        ]
    revisions = {case.identifier: case.revision + (1 if stale else 0) for case in cases}
    return ExecutionRecord.objects.create(
        run_id=f"TEST-{uuid4().hex}", owner=user, candidate=candidate, scenario=candidate.scenario,
        code_revision=candidate.code_revision, case_revisions=revisions, status=ExecutionRecord.COMPLETED,
        results=results, coverage_lines=int(coverage), coverage_considered=100, coverage_percent=coverage, scope_kind="full",
    )


def safe_candidate(user):
    candidate = Candidate.objects.get(code="CAND-CORRIGIDO")
    candidate.declared_fixes = []
    candidate.open_critical_defects = []
    candidate.changed_modules = ["cupons"]
    candidate.save()
    RiskPrediction.objects.filter(candidate=candidate).update(score=0.1)
    return candidate


@pytest.mark.django_db
@pytest.mark.engenharia
@pytest.mark.parametrize("coverage,expected", [(79.99, GateEvaluation.BLOCKED), (80.0, GateEvaluation.APPROVED), (80.01, GateEvaluation.APPROVED)])
def test_gate_coverage_boundary(demo_user, coverage, expected):
    candidate = safe_candidate(demo_user)
    full_execution(demo_user, candidate, coverage=coverage)
    assert evaluate_gate(demo_user, candidate).status == expected


@pytest.mark.django_db
@pytest.mark.engenharia
@pytest.mark.parametrize("risk,expected", [(0.799999, GateEvaluation.APPROVED), (0.8, GateEvaluation.BLOCKED), (0.800001, GateEvaluation.BLOCKED)])
def test_gate_risk_boundary_uses_full_precision(demo_user, risk, expected):
    candidate = safe_candidate(demo_user)
    RiskPrediction.objects.filter(candidate=candidate, module="cupons").update(score=risk)
    full_execution(demo_user, candidate, coverage=85)
    assert evaluate_gate(demo_user, candidate).status == expected


@pytest.mark.django_db
@pytest.mark.engenharia
def test_missing_mandatory_and_stale_revision_are_insufficient(demo_user):
    candidate = safe_candidate(demo_user)
    cases = list(demo_user.test_cases.filter(mandatory=True))
    partial_results = [{"identifier": case.identifier, "requirement_id": case.requirement_id, "revision": case.revision, "outcome": "passed"} for case in cases[:-1]]
    full_execution(demo_user, candidate, coverage=90, results=partial_results)
    assert evaluate_gate(demo_user, candidate).status == GateEvaluation.INSUFFICIENT
    full_execution(demo_user, candidate, coverage=90, stale=True)
    assert evaluate_gate(demo_user, candidate).status == GateEvaluation.INSUFFICIENT


@pytest.mark.django_db
@pytest.mark.engenharia
def test_known_critical_defect_wins_over_missing_evidence(demo_user):
    candidate = safe_candidate(demo_user)
    candidate.open_critical_defects = ["BUG-003"]
    candidate.save()
    assert evaluate_gate(demo_user, candidate).status == GateEvaluation.BLOCKED


@pytest.mark.django_db
@pytest.mark.engenharia
def test_unavailable_model_is_not_replaced_by_zero(demo_user, tmp_path):
    candidate = safe_candidate(demo_user)
    full_execution(demo_user, candidate, coverage=90)
    with override_settings(LAB_MODEL_PATH=tmp_path / "missing.joblib", LAB_MODEL_METADATA_PATH=tmp_path / "missing.json"):
        evaluation = evaluate_gate(demo_user, candidate)
    assert evaluation.status == GateEvaluation.INSUFFICIENT
    risk_rule = next(rule for rule in evaluation.rule_results if rule["rule"] == "Risco predito")
    assert risk_rule["status"] == "missing"


@pytest.mark.django_db
@pytest.mark.engenharia
def test_correction_requires_same_case_failure_and_pass(demo_user):
    candidate = Candidate.objects.get(code="CAND-CORRIGIDO")
    case = demo_user.test_cases.get(identifier="T-CUP-EXPIRADO")
    full_execution(demo_user, candidate, coverage=90, results=[{"identifier": case.identifier, "requirement_id": case.requirement_id, "revision": case.revision, "outcome": "passed", "expected": case.expected}])
    defective = Candidate.objects.get(code="CAND-DEFEITOS")
    ExecutionRecord.objects.create(
        run_id=f"DEFECT-{uuid4().hex}", owner=demo_user, candidate=defective, scenario=defective.scenario,
        code_revision=candidate.code_revision, case_revisions={case.identifier: case.revision}, status=ExecutionRecord.COMPLETED,
        results=[{"identifier": case.identifier, "requirement_id": case.requirement_id, "revision": case.revision, "outcome": "failed", "expected": case.expected}],
        coverage_lines=1, coverage_considered=2, coverage_percent=50, scope_kind="selection",
    )
    evidence = correction_evidence(demo_user, candidate, "BUG-001")
    assert evidence["verified"] is True
    assert evidence["test_identifier"] == case.identifier


@pytest.mark.django_db
@pytest.mark.engenharia
def test_rule_bot_quotes_evidence_and_cannot_change_gate(demo_user):
    candidate = safe_candidate(demo_user)
    RiskPrediction.objects.filter(candidate=candidate, module="cupons").update(score=0.9)
    full_execution(demo_user, candidate, coverage=90)
    evaluation = evaluate_gate(demo_user, candidate)
    response = answer(demo_user, candidate, "module")
    assert evaluation.status == GateEvaluation.BLOCKED
    assert "cupons" in response and "0.900000" in response
    assert GateEvaluation.objects.filter(pk=evaluation.pk, status=GateEvaluation.BLOCKED).exists()


@pytest.mark.django_db
@pytest.mark.engenharia
def test_rule_bot_answers_each_supported_question_from_records(demo_user):
    candidate = safe_candidate(demo_user)
    RiskPrediction.objects.filter(candidate=candidate, module="cupons").update(score=0.9)
    execution = full_execution(demo_user, candidate, coverage=79)
    evaluation = evaluate_gate(demo_user, candidate)
    assert evaluation.status == GateEvaluation.BLOCKED
    assert evaluation.evidence_snapshot["execution_run_id"] == execution.run_id
    for action in ("blocked", "module", "tests", "fixes", "coverage", "missing"):
        response = answer(demo_user, candidate, action)
        assert isinstance(response, str) and response
    assert "desconhecida" in answer(demo_user, candidate, "other")


@pytest.mark.django_db
@pytest.mark.engenharia
def test_rule_bot_states_when_evaluation_is_missing(demo_user):
    candidate = Candidate.objects.get(code="CAND-CORRIGIDO")
    assert "Ainda nao existe" in answer(demo_user, candidate, "blocked")
