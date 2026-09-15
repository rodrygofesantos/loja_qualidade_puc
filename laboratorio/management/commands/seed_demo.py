from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from laboratorio.ml import MODEL_VERSION, predict_risk
from laboratorio.models import Candidate, GateConfig, LabReport, RiskPrediction, Scenario, TestCase, UserLabState
from laboratorio.scenarios import BUGS
from loja.models import Cart, Category, Coupon, Customer, Product


CASES = [
    {"identifier": "T-CAT-INATIVO", "requirement_id": "REQ-CAT-001", "description": "Rejeita produto inativo", "scenario_type": "mandatory", "operation": "checkout", "inputs": {"active": False, "quantity": 1}, "expected": {"accepted": False, "requirement_id": "REQ-CAT-001"}},
    {"identifier": "T-CAR-QUANTIDADE", "requirement_id": "REQ-CAR-001", "description": "Rejeita quantidade zero", "scenario_type": "mandatory", "operation": "checkout", "inputs": {"quantity": 0}, "expected": {"accepted": False, "requirement_id": "REQ-CAR-001"}},
    {"identifier": "T-CUP-EXPIRADO", "requirement_id": "REQ-CUP-001", "description": "Rejeita cupom vencido no instante fixo", "scenario_type": "mandatory", "operation": "apply_coupon", "inputs": {"coupon_code": "EXPIRADO10", "items": [{"unit_price_cents": 10000, "quantity": 1}]}, "expected": {"accepted": False, "requirement_id": "REQ-CUP-001"}},
    {"identifier": "T-CUP-PERCENTUAL", "requirement_id": "REQ-CUP-002", "description": "Calcula 20% sobre R$ 100,00", "scenario_type": "mandatory", "operation": "apply_coupon", "inputs": {"coupon_code": "PUC20", "items": [{"unit_price_cents": 10000, "quantity": 1}]}, "expected": {"subtotal_cents": 10000, "discount_cents": 2000, "total_cents": 8000}},
    {"identifier": "T-CUP-FIXO", "requirement_id": "REQ-CUP-002", "description": "Aplica desconto fixo em centavos", "scenario_type": "mandatory", "operation": "apply_coupon", "inputs": {"coupon_code": "FIXO15", "items": [{"unit_price_cents": 10000, "quantity": 1}]}, "expected": {"discount_cents": 1500, "total_cents": 8500}},
    {"identifier": "T-CUP-INEXISTENTE", "requirement_id": "REQ-CUP-001", "description": "Rejeita cupom inexistente", "scenario_type": "mandatory", "operation": "apply_coupon", "inputs": {"coupon_code": "NAO-EXISTE", "items": [{"unit_price_cents": 10000, "quantity": 1}]}, "expected": {"accepted": False, "requirement_id": "REQ-CUP-001"}},
    {"identifier": "T-EST-LIMITE", "requirement_id": "REQ-EST-001", "description": "Rejeita seis unidades com estoque cinco", "scenario_type": "mandatory", "operation": "check_stock", "inputs": {"stock": 5, "quantity": 6}, "expected": {"accepted": False, "order_count": 0, "stock_after": 5}},
    {"identifier": "T-PED-RECALCULO", "requirement_id": "REQ-PED-001", "description": "Recalcula total apos mudar uma para duas unidades", "scenario_type": "mandatory", "operation": "checkout", "inputs": {"initial_quantity": 1, "quantity": 2, "unit_price_cents": 10000, "stock": 5}, "expected": {"accepted": True, "subtotal_cents": 20000, "total_cents": 20000}},
    {"identifier": "T-PED-IDEMPOTENCIA", "requirement_id": "REQ-PED-002", "description": "Repete checkout com a mesma chave", "scenario_type": "mandatory", "operation": "repeat_checkout", "inputs": {"quantity": 1, "stock": 5, "idempotency_key": "MESMA-CHAVE"}, "expected": {"order_count": 1, "stock_after": 4, "same_order": True, "created_second": False}},
    {"identifier": "T-PAG-RECUSA", "requirement_id": "REQ-PAG-001", "description": "Pagamento recusado nao consome estoque", "scenario_type": "mandatory", "operation": "payment", "inputs": {"quantity": 1, "stock": 5, "payment_action": "recusar"}, "expected": {"status": "refused", "stock_after": 5}},
    {"identifier": "T-FRACO-DESCONTO", "requirement_id": "REQ-CUP-002", "description": "Teste fraco: apenas verifica que o cupom foi aceito", "scenario_type": "regression", "operation": "apply_coupon", "inputs": {"coupon_code": "PUC20", "items": [{"unit_price_cents": 10000, "quantity": 1}]}, "expected": {"accepted": True}, "mandatory": False},
]


class Command(BaseCommand):
    help = "Cria ou atualiza os dados demonstrativos sem apagar progresso."

    def handle(self, *args, **options):
        User = get_user_model()
        user, _ = User.objects.get_or_create(username="aluno", defaults={"email": "aluno@example.invalid"})
        user.set_password("Qualidade2026!")
        user.save(update_fields=["password"])
        category_specs = [("Bebidas", "bebidas"), ("Livros", "livros"), ("Acessorios", "acessorios")]
        categories = {}
        for name, slug in category_specs:
            categories[slug], _ = Category.objects.get_or_create(slug=slug, defaults={"name": name})
        products = [
            ("SKU-CAFE", "Cafe didatico", "Cafe ficticio para cenarios de fronteira.", "bebidas", 10000, 5, True),
            ("SKU-LIVRO", "Livro de qualidade", "Exemplar ficticio sobre testes orientados a risco.", "livros", 6500, 12, True),
            ("SKU-CADERNO", "Caderno de evidencias", "Caderno ficticio para anotar decisoes.", "acessorios", 2850, 20, True),
            ("SKU-INATIVO", "Produto descontinuado", "Usado no REQ-CAT-001.", "acessorios", 1000, 3, False),
        ]
        for sku, name, description, category, price, stock, active in products:
            Product.objects.get_or_create(sku=sku, defaults={"name": name, "description": description, "category": categories[category], "price_cents": price, "stock": stock, "active": active})
        fixed_now = timezone.make_aware(datetime.fromisoformat("2026-06-15T12:00:00"), timezone.get_current_timezone())
        coupons = [
            ("PUC20", "percent", 20, 0, 5000, fixed_now.replace(year=2025), fixed_now.replace(year=2027), True),
            ("EXPIRADO10", "percent", 10, 0, None, fixed_now.replace(year=2024), fixed_now.replace(year=2025), True),
            ("FIXO15", "fixed", 1500, 5000, None, fixed_now.replace(year=2025), fixed_now.replace(year=2027), True),
        ]
        for code, kind, value, minimum, cap, start, end, active in coupons:
            Coupon.objects.get_or_create(code=code, defaults={"kind": kind, "value": value, "minimum_cents": minimum, "max_discount_cents": cap, "valid_from": start, "valid_until": end, "active": active})
        Customer.objects.get_or_create(owner=user, email="cliente@example.invalid", defaults={"name": "Marina Demo", "city": "Belo Horizonte", "notes": "Pessoa inteiramente ficticia"})
        Cart.objects.get_or_create(owner=user)
        scenario_specs = [
            ("defeitos", "Conjunto com defeitos", list(BUGS), "Ativa os cinco defeitos para investigacao."),
            ("corrigido", "Conjunto corrigido", [], "Implementacao de referencia de todas as regras."),
        ] + [(bug.lower().replace("-", ""), f"Demonstracao {bug}", [bug], BUGS[bug]["name"]) for bug in BUGS]
        scenarios = {}
        for code, name, bug_ids, description in scenario_specs:
            scenarios[code], _ = Scenario.objects.update_or_create(code=code, defaults={"name": name, "bug_ids": bug_ids, "description": description, "revision": "scenario-v1"})
        candidate_specs = [
            ("CAND-DEFEITOS", "Build com defeitos", "Contem os cinco defeitos intencionais.", "defeitos", ["cupons", "carrinho", "estoque", "checkout"], ["BUG-003"], []),
            ("CAND-CORRIGIDO", "Build corrigida de baixo risco", "Referencia corrigida; exige evidencias atuais.", "corrigido", ["cupons", "carrinho"], [], list(BUGS)),
            ("CAND-ALTO-RISCO", "Build corrigida com risco alto", "Regras corrigidas, mas modulo muito alterado permanece bloqueado pelo modelo.", "corrigido", ["checkout"], [], list(BUGS)),
        ]
        candidates = {}
        for code, name, description, scenario_code, modules, critical, fixes in candidate_specs:
            candidates[code], _ = Candidate.objects.update_or_create(code=code, defaults={"name": name, "description": description, "scenario": scenarios[scenario_code], "changed_modules": modules, "open_critical_defects": critical, "declared_fixes": fixes, "code_revision": "lab-v1"})
        UserLabState.objects.get_or_create(user=user, defaults={"scenario": scenarios["defeitos"], "candidate": candidates["CAND-DEFEITOS"]})
        LabReport.objects.get_or_create(owner=user)
        GateConfig.objects.get_or_create(version=1, defaults={"coverage_threshold": 80.0, "risk_threshold": 0.8, "note": "Criterios iniciais do laboratorio", "created_by": user})
        for spec in CASES:
            defaults = {key: value for key, value in spec.items() if key != "identifier"}
            defaults.setdefault("mandatory", True)
            defaults.update({"schema_version": "1.0", "reviewed": True, "review_notes": "Oraculo obrigatorio revisado no material do professor."})
            existing = TestCase.objects.filter(owner=user, identifier=spec["identifier"]).first()
            if existing is not None:
                versioned_fields = ("requirement_id", "description", "scenario_type", "operation", "inputs", "expected", "mandatory")
                if any(getattr(existing, field) != defaults[field] for field in versioned_fields):
                    defaults["revision"] = existing.revision + 1
            TestCase.objects.update_or_create(owner=user, identifier=spec["identifier"], defaults=defaults)
        feature_profiles = {
            "CAND-DEFEITOS": {"churn_lines": 520, "commit_frequency": 9, "size_loc": 1800, "previous_defects": 3},
            "CAND-CORRIGIDO": {"churn_lines": 18, "commit_frequency": 1, "size_loc": 220, "previous_defects": 0},
            "CAND-ALTO-RISCO": {"churn_lines": 980, "commit_frequency": 14, "size_loc": 3600, "previous_defects": 5},
        }
        try:
            for code, candidate in candidates.items():
                for module in candidate.changed_modules:
                    features = feature_profiles[code]
                    score, explanation, metadata = predict_risk(features)
                    RiskPrediction.objects.update_or_create(candidate=candidate, module=module, model_version=metadata["model_version"], defaults={"features": features, "score": score, "explanation": explanation})
        except RuntimeError as exc:
            self.stdout.write(self.style.WARNING(str(exc)))
        self.stdout.write(self.style.SUCCESS("Usuario aluno e dados demonstrativos preparados sem apagar progresso."))
