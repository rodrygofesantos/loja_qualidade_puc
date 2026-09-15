import subprocess

import pytest
from django.test import override_settings

from laboratorio.executor import execute_cases
from laboratorio.models import Candidate, TestExecution as ExecutionRecord
from loja.models import Order, Product


@pytest.mark.django_db(transaction=True)
@pytest.mark.engenharia
def test_executor_uses_temporary_database_and_real_coverage(demo_user, tmp_path):
    candidate = Candidate.objects.get(code="CAND-CORRIGIDO")
    case = demo_user.test_cases.get(identifier="T-PED-IDEMPOTENCIA")
    stock_before = Product.objects.get(sku="SKU-CAFE").stock
    with override_settings(LAB_EXECUTION_DIR=tmp_path):
        execution = execute_cases(demo_user, candidate, candidate.scenario, [case])
    assert execution.status == ExecutionRecord.COMPLETED
    assert execution.results[0]["outcome"] == "passed"
    assert execution.coverage_considered > 0
    assert execution.coverage_lines > 0
    assert execution.scope_kind == "selection"
    assert Product.objects.get(sku="SKU-CAFE").stock == stock_before
    assert Order.objects.filter(owner=demo_user).count() == 0
    assert not list(tmp_path.glob("*/execution.sqlite3*"))


@pytest.mark.django_db
@pytest.mark.engenharia
def test_timeout_is_executor_error_not_failed_test(demo_user, tmp_path, monkeypatch):
    candidate = Candidate.objects.get(code="CAND-CORRIGIDO")
    case = demo_user.test_cases.get(identifier="T-CUP-PERCENTUAL")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 1))

    monkeypatch.setattr("laboratorio.executor.subprocess.run", timeout)
    with override_settings(LAB_EXECUTION_DIR=tmp_path):
        execution = execute_cases(demo_user, candidate, candidate.scenario, [case], timeout=1)
    assert execution.status == ExecutionRecord.ERROR
    assert execution.results == []
    assert "Tempo limite" in execution.error_message
