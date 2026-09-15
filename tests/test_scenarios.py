from copy import deepcopy
from types import SimpleNamespace

import pytest

from laboratorio.case_adapter import run_one_case
from laboratorio.management.commands.seed_demo import CASES


CASE_BY_ID = {item["identifier"]: item for item in CASES}
BUG_CASES = {
    "BUG-001": "T-CUP-EXPIRADO",
    "BUG-002": "T-CUP-PERCENTUAL",
    "BUG-003": "T-EST-LIMITE",
    "BUG-004": "T-PED-RECALCULO",
    "BUG-005": "T-PED-IDEMPOTENCIA",
}


def prepared_case(identifier):
    case = deepcopy(CASE_BY_ID[identifier])
    case["revision"] = 1
    return case


@pytest.mark.django_db(transaction=True)
@pytest.mark.engenharia
@pytest.mark.parametrize("bug_id,case_id", BUG_CASES.items())
def test_each_defect_fails_the_same_oracle_that_passes_corrected(bug_id, case_id):
    case = prepared_case(case_id)
    defective = SimpleNamespace(code=bug_id.lower(), bug_ids=[bug_id])
    corrected = SimpleNamespace(code="corrigido", bug_ids=[])
    assert run_one_case(case, defective)["outcome"] == "failed"
    assert run_one_case(case, corrected)["outcome"] == "passed"


@pytest.mark.django_db(transaction=True)
@pytest.mark.engenharia
def test_weak_test_passes_despite_wrong_discount_but_strong_test_fails():
    bug2 = SimpleNamespace(code="bug002", bug_ids=["BUG-002"])
    assert run_one_case(prepared_case("T-FRACO-DESCONTO"), bug2)["outcome"] == "passed"
    strong = run_one_case(prepared_case("T-CUP-PERCENTUAL"), bug2)
    assert strong["outcome"] == "failed"
    assert strong["observed"]["discount_cents"] == 20
    assert strong["expected"]["discount_cents"] == 2000

