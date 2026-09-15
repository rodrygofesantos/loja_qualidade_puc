import json
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.urls import reverse

from laboratorio.models import Candidate, DataPreparationRun, GateConfig, GateEvaluation, LabReport, ReleaseSimulation, TestCase as CaseRecord
from loja.models import Customer, Order, Product


@pytest.mark.django_db
@pytest.mark.engenharia
def test_login_and_main_pages_render_in_portuguese(client, demo_user):
    response = client.post(reverse("login"), {"username": "aluno", "password": "Qualidade2026!"})
    assert response.status_code == 302
    urls = [
        reverse("laboratorio:overview"), reverse("loja:catalog"), reverse("loja:cart"), reverse("loja:customers"),
        reverse("loja:orders"), reverse("laboratorio:scenarios"), reverse("laboratorio:data_quality"),
        reverse("laboratorio:dashboard"), reverse("laboratorio:prediction"), reverse("laboratorio:test_cases"),
        reverse("laboratorio:executions"), reverse("laboratorio:coverage"), reverse("laboratorio:evidence"),
        reverse("laboratorio:gate"), reverse("laboratorio:bot"), reverse("laboratorio:report"), reverse("laboratorio:reset"),
    ]
    for url in urls:
        page = client.get(url)
        assert page.status_code == 200, url
        assert b"<!doctype html>" in page.content


@pytest.mark.django_db
@pytest.mark.engenharia
def test_smoke_navigation_purchase_and_order_history(client, demo_user):
    client.force_login(demo_user)
    state = demo_user.lab_state
    state.scenario = Candidate.objects.get(code="CAND-CORRIGIDO").scenario
    state.candidate = Candidate.objects.get(code="CAND-CORRIGIDO")
    state.save()
    product = Product.objects.get(sku="SKU-CAFE")
    customer = Customer.objects.get(owner=demo_user)
    assert client.post(reverse("loja:cart_add", args=[product.pk]), {"quantity": 1}).status_code == 302
    response = client.post(reverse("loja:checkout"), {"customer": customer.pk, "idempotency_key": "UI-SMOKE", "payment_action": "aprovar"})
    assert response.status_code == 302
    order = Order.objects.get(owner=demo_user)
    assert order.status == Order.CONFIRMED
    detail = client.get(reverse("loja:order_detail", args=[order.pk]))
    assert detail.status_code == 200
    assert b"UI-SMOKE" in detail.content


@pytest.mark.django_db
@pytest.mark.engenharia
def test_import_two_cases_then_requires_human_review(client, demo_user):
    client.force_login(demo_user)
    cases = []
    for number in (1, 2):
        cases.append({"identifier": f"IA-CASE-{number}", "requirement_id": "REQ-EST-001", "description": "Caso proposto", "scenario_type": "boundary", "operation": "check_stock", "inputs": {"stock": 5, "quantity": number}, "expected": {"accepted": True}})
    response = client.post(reverse("laboratorio:import_cases"), {"package": json.dumps({"schema_version": "1.0", "cases": cases})})
    assert response.status_code == 302
    imported = CaseRecord.objects.filter(owner=demo_user, identifier__startswith="IA-CASE")
    assert imported.count() == 2
    assert not imported.filter(reviewed=True).exists()
    case = imported.first()
    edit = client.post(reverse("laboratorio:edit_case", args=[case.pk]), {
        "identifier": case.identifier, "requirement_id": case.requirement_id, "description": case.description,
        "scenario_type": case.scenario_type, "operation": case.operation, "review_notes": "Cálculo conferido manualmente",
        "inputs_text": json.dumps(case.inputs), "expected_text": json.dumps(case.expected),
    })
    assert edit.status_code == 302
    case.refresh_from_db()
    assert case.reviewed is True and case.revision == 2


@pytest.mark.django_db
@pytest.mark.engenharia
def test_invalid_import_and_mandatory_overwrite_are_rejected(client, demo_user):
    client.force_login(demo_user)
    invalid = {"schema_version": "1.0", "cases": [{"identifier": "BAD", "requirement_id": "REQ-EST-001", "description": "x", "scenario_type": "boundary", "operation": "eval", "inputs": {}, "expected": {"x": 1}}]}
    response = client.post(reverse("laboratorio:import_cases"), {"package": json.dumps(invalid)}, follow=True)
    assert response.status_code == 200
    assert b"Pacote inv" in response.content
    mandatory = demo_user.test_cases.filter(mandatory=True).first()
    collision = {"schema_version": "1.0", "cases": [{"identifier": mandatory.identifier, "requirement_id": mandatory.requirement_id, "description": "sobrescrever", "scenario_type": "boundary", "operation": "check_stock", "inputs": {}, "expected": {"accepted": True}}]}
    response = client.post(reverse("laboratorio:import_cases"), {"package": json.dumps(collision)}, follow=True)
    assert b"obrigat" in response.content
    mandatory.refresh_from_db()
    assert mandatory.description != "sobrescrever"


@pytest.mark.django_db
@pytest.mark.engenharia
def test_data_decision_report_and_exports(client, demo_user):
    client.force_login(demo_user)
    response = client.post(reverse("laboratorio:data_quality"), {"decision_note": "Preservo inconsistências para manter a rastreabilidade."})
    assert response.status_code == 200
    assert DataPreparationRun.objects.filter(owner=demo_user).count() == 1
    report_payload = {
        "context": "Análise didática", "data_decision": "Marcar vínculo", "priority": "checkout",
        "visualization": "churn", "release_decision": "bloquear", "ai_tool": "Ferramenta livre",
        "human_checks": "Revisei os centavos", "prioridade": "on", "limites_da_predicao": "on",
    }
    assert client.post(reverse("laboratorio:report"), report_payload).status_code == 302
    markdown = client.get(reverse("laboratorio:report_export", args=["md"]))
    html = client.get(reverse("laboratorio:report_export", args=["html"]))
    package = client.get(reverse("laboratorio:context_export"))
    assert markdown.status_code == 200 and b"An" in markdown.content
    assert html.status_code == 200 and b"<!doctype html>" in html.content
    assert package.status_code == 200 and package["Content-Type"] == "application/zip"


@pytest.mark.django_db
@pytest.mark.engenharia
def test_release_endpoint_rejects_stale_evaluation(client, demo_user):
    client.force_login(demo_user)
    candidate = demo_user.lab_state.candidate
    old_config = GateConfig.objects.first()
    shown = GateEvaluation.objects.create(
        evaluation_id=f"GATE-{uuid4().hex}", owner=demo_user, candidate=candidate, config=old_config,
        status=GateEvaluation.APPROVED, rule_results=[], evidence_snapshot={"candidate_revision": candidate.code_revision},
    )
    GateConfig.objects.create(version=old_config.version + 1, coverage_threshold=80, risk_threshold=0.8, note="nova", created_by=demo_user)
    response = client.post(reverse("laboratorio:release"), {"evaluation_id": shown.evaluation_id}, follow=True)
    assert response.status_code == 200
    assert ReleaseSimulation.objects.count() == 0
    assert b"desatualizada" in response.content
