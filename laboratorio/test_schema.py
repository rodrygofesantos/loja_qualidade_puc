from copy import deepcopy
import re


SCHEMA_VERSION = "1.0"
ALLOWED_OPERATIONS = {"calculate_cart", "apply_coupon", "check_stock", "checkout", "payment", "repeat_checkout"}
ALLOWED_REQUIREMENTS = {
    "REQ-CAT-001", "REQ-CAR-001", "REQ-CUP-001", "REQ-CUP-002", "REQ-EST-001", "REQ-PED-001", "REQ-PED-002", "REQ-PAG-001"
}


class PackageValidationError(ValueError):
    """Erro de contrato seguro apresentado ao usuario sem executar o pacote."""


def validate_package(payload):
    if not isinstance(payload, dict):
        raise PackageValidationError("O pacote deve ser um objeto JSON.")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise PackageValidationError(f"schema_version deve ser {SCHEMA_VERSION}.")
    extra_package = set(payload).difference({"schema_version", "cases"})
    if extra_package:
        raise PackageValidationError(f"Campos desconhecidos no pacote: {', '.join(sorted(extra_package))}.")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 10:
        raise PackageValidationError("Forneca entre 1 e 10 casos; a atividade pede dois.")
    identifiers = set()
    clean = []
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise PackageValidationError(f"Caso {index} deve ser um objeto.")
        required = {"identifier", "requirement_id", "description", "scenario_type", "operation", "inputs", "expected"}
        missing = required.difference(case)
        if missing:
            raise PackageValidationError(f"Caso {index}: campos ausentes: {', '.join(sorted(missing))}.")
        extra = set(case).difference(required)
        if extra:
            raise PackageValidationError(f"Caso {index}: campos desconhecidos: {', '.join(sorted(extra))}.")
        identifier = case["identifier"]
        if not isinstance(identifier, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,60}", identifier) is None:
            raise PackageValidationError(f"Caso {index}: identifier invalido.")
        if identifier in identifiers:
            raise PackageValidationError(f"Identifier duplicado: {identifier}.")
        identifiers.add(identifier)
        if case["requirement_id"] not in ALLOWED_REQUIREMENTS:
            raise PackageValidationError(f"Caso {identifier}: requisito nao suportado.")
        if case["operation"] not in ALLOWED_OPERATIONS:
            raise PackageValidationError(f"Caso {identifier}: operacao nao permitida.")
        if case["scenario_type"] not in {"relevant_risk", "boundary", "exception", "regression", "mandatory"}:
            raise PackageValidationError(f"Caso {identifier}: tipo de cenario invalido.")
        if not isinstance(case["description"], str) or not 1 <= len(case["description"].strip()) <= 240:
            raise PackageValidationError(f"Caso {identifier}: description deve ter de 1 a 240 caracteres.")
        if not isinstance(case["inputs"], dict) or not isinstance(case["expected"], dict):
            raise PackageValidationError(f"Caso {identifier}: inputs e expected devem ser objetos.")
        if not case["expected"]:
            raise PackageValidationError(f"Caso {identifier}: expected nao pode ser vazio.")
        allowed_inputs = {"items", "coupon_code", "unit_price_cents", "quantity", "initial_quantity", "stock", "active", "idempotency_key", "payment_action"}
        unexpected_inputs = set(case["inputs"]).difference(allowed_inputs)
        if unexpected_inputs:
            raise PackageValidationError(f"Caso {identifier}: entradas desconhecidas: {', '.join(sorted(unexpected_inputs))}.")
        for field in ("unit_price_cents", "quantity", "initial_quantity", "stock"):
            value = case["inputs"].get(field)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise PackageValidationError(f"Caso {identifier}: {field} deve ser inteiro.")
        if "active" in case["inputs"] and not isinstance(case["inputs"]["active"], bool):
            raise PackageValidationError(f"Caso {identifier}: active deve ser booleano.")
        if "coupon_code" in case["inputs"] and (not isinstance(case["inputs"]["coupon_code"], str) or len(case["inputs"]["coupon_code"]) > 30):
            raise PackageValidationError(f"Caso {identifier}: coupon_code invalido.")
        if "idempotency_key" in case["inputs"] and (not isinstance(case["inputs"]["idempotency_key"], str) or len(case["inputs"]["idempotency_key"]) > 64):
            raise PackageValidationError(f"Caso {identifier}: idempotency_key invalida.")
        if case["inputs"].get("payment_action", "aprovar") not in {"aprovar", "recusar"}:
            raise PackageValidationError(f"Caso {identifier}: payment_action invalida.")
        if "items" in case["inputs"]:
            items = case["inputs"]["items"]
            if not isinstance(items, list) or not 1 <= len(items) <= 20:
                raise PackageValidationError(f"Caso {identifier}: items deve conter de 1 a 20 itens.")
            for item in items:
                if not isinstance(item, dict) or set(item) != {"unit_price_cents", "quantity"}:
                    raise PackageValidationError(f"Caso {identifier}: cada item requer somente unit_price_cents e quantity.")
                if any(isinstance(item[field], bool) or not isinstance(item[field], int) for field in item):
                    raise PackageValidationError(f"Caso {identifier}: preco e quantidade dos itens devem ser inteiros.")
        if len(str(case["inputs"])) > 8000 or len(str(case["expected"])) > 4000:
            raise PackageValidationError(f"Caso {identifier}: conteudo excede o limite.")
        clean.append({key: deepcopy(case[key]) for key in required})
    return {"schema_version": SCHEMA_VERSION, "cases": clean}


def prompt_context(scenario, candidate):
    return f"""Voce e uma IA auxiliando revisao de testes, nao definindo o oraculo final.
Crie exatamente dois casos JSON no schema 1.0: um relevante ao risco e outro de fronteira, excecao ou regressao.
Candidato: {candidate.code} - {candidate.name}
Cenario selecionado: {scenario.code}; defeitos ativos: {', '.join(scenario.bug_ids) or 'nenhum'}.
Regras: quantidades inteiras positivas; dinheiro em centavos; cupom valido no intervalo inclusivo; estoque nao pode ser excedido; pagamento recusado nao consome estoque; chave repetida cria um unico pedido.
Operacoes permitidas: calculate_cart, apply_coupon, check_stock, checkout, payment, repeat_checkout.
Campos por caso: identifier, requirement_id, description, scenario_type, operation, inputs, expected.
Use apenas dados ficticios, por exemplo SKU-CAFE (10000 centavos, estoque 5), PUC20 e EXPIRADO10.
Responda somente com: {{"schema_version":"1.0","cases":[...]}}.
O humano revisara requisito e resultados esperados antes da execucao."""
