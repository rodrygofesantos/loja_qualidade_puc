import pytest

from laboratorio.test_schema import PackageValidationError, validate_package


def valid_case(identifier):
    return {"identifier": identifier, "requirement_id": "REQ-EST-001", "description": "Limite", "scenario_type": "boundary", "operation": "check_stock", "inputs": {"stock": 5, "quantity": 5}, "expected": {"accepted": True}}


@pytest.mark.engenharia
def test_imports_two_valid_cases():
    package = validate_package({"schema_version": "1.0", "cases": [valid_case("IA-1"), valid_case("IA-2")]})
    assert [case["identifier"] for case in package["cases"]] == ["IA-1", "IA-2"]


@pytest.mark.engenharia
@pytest.mark.parametrize("mutation", ["version", "operation", "missing", "duplicate"])
def test_rejects_invalid_packages(mutation):
    package = {"schema_version": "1.0", "cases": [valid_case("IA-1")]}
    if mutation == "version":
        package["schema_version"] = "2.0"
    elif mutation == "operation":
        package["cases"][0]["operation"] = "run_python"
    elif mutation == "missing":
        package["cases"][0].pop("expected")
    else:
        package["cases"].append(valid_case("IA-1"))
    with pytest.raises(PackageValidationError):
        validate_package(package)


@pytest.mark.engenharia
@pytest.mark.parametrize(
    "mutation",
    [
        "not_object", "package_extra", "case_extra", "identifier", "requirement", "scenario", "description",
        "expected_type", "expected_empty", "input_extra", "integer_type", "active_type", "coupon_code",
        "idempotency_key", "payment_action", "items_empty", "item_fields", "item_types", "oversized",
    ],
)
def test_rejects_unknown_fields_and_unsafe_input_types(mutation):
    package = {"schema_version": "1.0", "cases": [valid_case("SAFE-1")]}
    case = package["cases"][0]
    if mutation == "not_object":
        package = []
    elif mutation == "package_extra":
        package["command"] = "anything"
    elif mutation == "case_extra":
        case["python"] = "anything"
    elif mutation == "identifier":
        case["identifier"] = "fora do padrão"
    elif mutation == "requirement":
        case["requirement_id"] = "REQ-UNKNOWN"
    elif mutation == "scenario":
        case["scenario_type"] = "arbitrary"
    elif mutation == "description":
        case["description"] = "x" * 241
    elif mutation == "expected_type":
        case["expected"] = []
    elif mutation == "expected_empty":
        case["expected"] = {}
    elif mutation == "input_extra":
        case["inputs"]["path"] = "/tmp/script.py"
    elif mutation == "integer_type":
        case["inputs"]["quantity"] = "5"
    elif mutation == "active_type":
        case["inputs"]["active"] = "yes"
    elif mutation == "coupon_code":
        case["inputs"]["coupon_code"] = "X" * 31
    elif mutation == "idempotency_key":
        case["inputs"]["idempotency_key"] = "X" * 65
    elif mutation == "payment_action":
        case["inputs"]["payment_action"] = "cobrar_cartao"
    elif mutation == "items_empty":
        case["inputs"]["items"] = []
    elif mutation == "item_fields":
        case["inputs"]["items"] = [{"unit_price_cents": 10, "quantity": 1, "call": "os.system"}]
    elif mutation == "item_types":
        case["inputs"]["items"] = [{"unit_price_cents": 10, "quantity": "1"}]
    else:
        case["expected"] = {"detail": "x" * 5000}
    with pytest.raises(PackageValidationError):
        validate_package(package)
