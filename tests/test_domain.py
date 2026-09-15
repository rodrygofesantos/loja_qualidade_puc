from datetime import datetime
from types import SimpleNamespace

import pytest
from django.utils import timezone

from laboratorio.scenarios import policy_for
from loja.domain import BusinessRuleError, CouponData, calculate_totals, subtotal_cents


NOW = timezone.make_aware(datetime.fromisoformat("2026-06-15T12:00:00"), timezone.get_current_timezone())


def coupon(code="PUC20", kind="percent", value=20, active=True, start_year=2025, end_year=2027, minimum=0, cap=None):
    return CouponData(code, kind, value, minimum, cap, active, NOW.replace(year=start_year), NOW.replace(year=end_year))


@pytest.mark.engenharia
def test_subtotal_uses_integer_cents_and_rejects_invalid_quantity():
    assert subtotal_cents([{"unit_price_cents": 1999, "quantity": 3}, {"unit_price_cents": 2, "quantity": 2}]) == 6001
    for invalid in (0, -1, 1.5, True, "2"):
        with pytest.raises(BusinessRuleError, match="inteiro positivo"):
            subtotal_cents([{"unit_price_cents": 100, "quantity": invalid}])


@pytest.mark.engenharia
def test_discount_oracles_are_independent_and_capped():
    corrected = policy_for(SimpleNamespace(code="corrigido", bug_ids=[]))
    assert calculate_totals([{"unit_price_cents": 10000, "quantity": 1}], coupon(cap=1500), NOW, corrected) == {
        "subtotal_cents": 10000,
        "discount_cents": 1500,
        "total_cents": 8500,
    }
    assert calculate_totals([{"unit_price_cents": 1000, "quantity": 1}], coupon(kind="fixed", value=5000), NOW, corrected)["total_cents"] == 0


@pytest.mark.engenharia
def test_bug_001_and_bug_002_are_explicit_policy_differences():
    corrected = policy_for(SimpleNamespace(code="corrigido", bug_ids=[]))
    expired = coupon(code="EXPIRADO10", value=10, start_year=2024, end_year=2025)
    with pytest.raises(BusinessRuleError) as error:
        calculate_totals([{"unit_price_cents": 10000, "quantity": 1}], expired, NOW, corrected)
    assert error.value.requirement == "REQ-CUP-001"
    bug1 = policy_for(SimpleNamespace(code="bug001", bug_ids=["BUG-001"]))
    assert calculate_totals([{"unit_price_cents": 10000, "quantity": 1}], expired, NOW, bug1)["discount_cents"] == 1000
    bug2 = policy_for(SimpleNamespace(code="bug002", bug_ids=["BUG-002"]))
    assert calculate_totals([{"unit_price_cents": 10000, "quantity": 1}], coupon(), NOW, bug2)["discount_cents"] == 20
    assert calculate_totals([{"unit_price_cents": 10000, "quantity": 1}], coupon(), NOW, corrected)["discount_cents"] == 2000

