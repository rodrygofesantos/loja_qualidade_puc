from uuid import uuid4

import pytest

from laboratorio.activity import build_activity_summary
from laboratorio.gate import evaluate_gate, evaluation_freshness
from laboratorio.models import Candidate, GateEvaluation, TestExecution as ExecutionRecord


def make_execution(user, candidate, scenario, results, *, scope="selection", coverage=75.0):
    return ExecutionRecord.objects.create(
        run_id=f"ACTIVITY-{uuid4().hex}",
        owner=user,
        candidate=candidate,
        scenario=scenario,
        scenario_revision=scenario.revision,
        code_revision=candidate.code_revision,
        case_revisions={item["identifier"]: item["revision"] for item in results},
        status=ExecutionRecord.COMPLETED,
        results=results,
        coverage_lines=int(coverage),
        coverage_considered=100,
        coverage_percent=coverage,
        scope_kind=scope,
    )


@pytest.mark.django_db
@pytest.mark.engenharia
def test_initial_activity_summary_never_treats_missing_evidence_as_success(demo_user):
    summary = build_activity_summary(demo_user, demo_user.lab_state)

    assert summary["scenario_bug_count"] == 5
    assert summary["tests"] == {
        "total": 10,
        "executed": 0,
        "passed": 0,
        "failed": 0,
        "not_run": 10,
        "full_execution": None,
    }
    assert summary["gate_label"] == "Não avaliado"
    assert summary["coverage"] is None
    assert summary["completed_count"] == 1
    assert summary["next_action"]["label"] == "Iniciar atividade"


@pytest.mark.django_db
@pytest.mark.engenharia
def test_test_summary_uses_latest_compatible_result_for_each_current_case(demo_user):
    state = demo_user.lab_state
    first, second = list(demo_user.test_cases.filter(mandatory=True)[:2])
    make_execution(
        demo_user,
        state.candidate,
        state.scenario,
        [
            {"identifier": first.identifier, "revision": first.revision, "outcome": "passed"},
            {"identifier": second.identifier, "revision": second.revision, "outcome": "passed"},
        ],
    )
    make_execution(
        demo_user,
        state.candidate,
        state.scenario,
        [
            {"identifier": first.identifier, "revision": first.revision, "outcome": "failed"},
            {"identifier": second.identifier, "revision": second.revision, "outcome": "not_run"},
        ],
    )

    tests = build_activity_summary(demo_user, state)["tests"]

    assert tests["executed"] == 1
    assert tests["passed"] == 0
    assert tests["failed"] == 1
    assert tests["not_run"] == 9


@pytest.mark.django_db
@pytest.mark.engenharia
def test_gate_becomes_stale_when_selected_scenario_changes(demo_user):
    state = demo_user.lab_state
    evaluation = evaluate_gate(demo_user, state.candidate)
    assert evaluation.status == GateEvaluation.BLOCKED
    assert evaluation_freshness(demo_user, state, evaluation) == (True, [])

    state.scenario = Candidate.objects.get(code="CAND-CORRIGIDO").scenario
    state.save(update_fields=["scenario", "updated_at"])

    is_current, reasons = evaluation_freshness(demo_user, state, evaluation)
    assert is_current is False
    assert any("cenário" in reason for reason in reasons)


@pytest.mark.django_db
@pytest.mark.engenharia
def test_gate_becomes_stale_after_new_full_execution(demo_user):
    state = demo_user.lab_state
    cases = list(demo_user.test_cases.filter(mandatory=True))
    results = [
        {
            "identifier": case.identifier,
            "requirement_id": case.requirement_id,
            "revision": case.revision,
            "outcome": "passed",
            "expected": case.expected,
            "observed": case.expected,
        }
        for case in cases
    ]
    make_execution(demo_user, state.candidate, state.scenario, results, scope="full", coverage=85)
    evaluation = evaluate_gate(demo_user, state.candidate)
    assert evaluation_freshness(demo_user, state, evaluation) == (True, [])

    make_execution(demo_user, state.candidate, state.scenario, results, scope="full", coverage=86)
    is_current, reasons = evaluation_freshness(demo_user, state, evaluation)

    assert is_current is False
    assert any("execução completa mais recente" in reason for reason in reasons)


@pytest.mark.django_db
@pytest.mark.engenharia
def test_overview_exposes_semantic_navigation_and_stale_gate(client, demo_user):
    client.force_login(demo_user)
    evaluation = evaluate_gate(demo_user, demo_user.lab_state.candidate)
    assert evaluation.status == GateEvaluation.BLOCKED
    corrected = Candidate.objects.get(code="CAND-CORRIGIDO")
    state = demo_user.lab_state
    state.scenario = corrected.scenario
    state.save(update_fields=["scenario", "updated_at"])

    response = client.get("/")

    assert response.status_code == 200
    assert b'aria-current="page"' in response.content
    assert "Métricas" in response.content.decode()
    assert "Assistente" in response.content.decode()
    assert "Avaliação desatualizada" in response.content.decode()
    assert "Defeitos intencionais ativos" in response.content.decode()
