from datetime import datetime
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from laboratorio.scenarios import policy_for
from loja.domain import BusinessRuleError, CouponData, calculate_totals
from loja.models import Category, Coupon, Customer, Order, Product
from loja.services import add_to_cart, apply_coupon, checkout, get_cart, serialize_order, update_cart_item


FIXED_NOW = timezone.make_aware(datetime.fromisoformat("2026-06-15T12:00:00"), timezone.get_current_timezone())


def _seed_case(inputs):
    User = get_user_model()
    user = User.objects.create_user(username=f"runner-{User.objects.count()+1}", password="unused")
    category = Category.objects.create(name=f"Categoria {user.pk}", slug=f"categoria-{user.pk}")
    item_spec = (inputs.get("items") or [{}])[0]
    product = Product.objects.create(
        sku="SKU-CAFE",
        name="Cafe didatico",
        description="Produto ficticio",
        category=category,
        price_cents=int(inputs.get("unit_price_cents", item_spec.get("unit_price_cents", 10000))),
        stock=int(inputs.get("stock", 5)),
        active=bool(inputs.get("active", True)),
    )
    customer = Customer.objects.create(owner=user, name="Cliente Teste", email="teste@example.invalid", city="Curitiba")
    Coupon.objects.create(code="PUC20", kind="percent", value=20, minimum_cents=0, max_discount_cents=5000, active=True, valid_from=FIXED_NOW.replace(year=2025), valid_until=FIXED_NOW.replace(year=2027))
    Coupon.objects.create(code="EXPIRADO10", kind="percent", value=10, minimum_cents=0, active=True, valid_from=FIXED_NOW.replace(year=2024), valid_until=FIXED_NOW.replace(year=2025))
    Coupon.objects.create(code="FIXO15", kind="fixed", value=1500, minimum_cents=5000, active=True, valid_from=FIXED_NOW.replace(year=2025), valid_until=FIXED_NOW.replace(year=2027))
    return user, product, customer


def _coupon_from_code(code):
    if not code:
        return None
    item = Coupon.objects.get(code=code)
    return CouponData(item.code, item.kind, item.value, item.minimum_cents, item.max_discount_cents, item.active, item.valid_from, item.valid_until)


def _matches(expected, observed):
    return all(key in observed and observed[key] == value for key, value in expected.items())


def run_one_case(case, scenario):
    expected = case["expected"]
    inputs = case["inputs"]
    observed = {}
    outcome = "not_run"
    try:
        with transaction.atomic():
            user, product, customer = _seed_case(inputs)
            operation = case["operation"]
            if operation == "calculate_cart":
                items = inputs.get("items", [{"unit_price_cents": inputs.get("unit_price_cents", 10000), "quantity": inputs.get("quantity", 1)}])
                coupon = _coupon_from_code(inputs.get("coupon_code", ""))
                observed = {"accepted": True, **calculate_totals(items, coupon, FIXED_NOW, policy_for(scenario))}
            elif operation == "apply_coupon":
                item_spec = (inputs.get("items") or [{}])[0]
                add_to_cart(user, product, item_spec.get("quantity", inputs.get("quantity", 1)), scenario)
                apply_coupon(get_cart(user), inputs.get("coupon_code", ""), scenario, now=FIXED_NOW)
                observed = {"accepted": True, **calculate_totals(
                    [{"unit_price_cents": product.price_cents, "quantity": item_spec.get("quantity", inputs.get("quantity", 1))}],
                    _coupon_from_code(inputs.get("coupon_code", "")), FIXED_NOW, policy_for(scenario)
                )}
            elif operation in {"check_stock", "checkout", "payment", "repeat_checkout"}:
                initial_quantity = int(inputs.get("initial_quantity", inputs.get("quantity", 1)))
                add_to_cart(user, product, initial_quantity, scenario)
                quantity = int(inputs.get("quantity", initial_quantity))
                if quantity != initial_quantity:
                    update_cart_item(get_cart(user).items.get(), quantity, scenario)
                if inputs.get("coupon_code"):
                    apply_coupon(get_cart(user), inputs["coupon_code"], scenario, now=FIXED_NOW)
                key = str(inputs.get("idempotency_key", "CASE-KEY"))
                action = str(inputs.get("payment_action", "aprovar"))
                first, _ = checkout(user, customer, scenario, key, action, now=FIXED_NOW)
                if operation == "repeat_checkout":
                    second, created_second = checkout(user, customer, scenario, key, action, now=FIXED_NOW)
                    observed = {
                        "accepted": True,
                        "order_count": Order.objects.filter(owner=user).count(),
                        "stock_after": Product.objects.get(pk=product.pk).stock,
                        "same_order": first.pk == second.pk,
                        "created_second": created_second,
                    }
                else:
                    observed = {"accepted": True, **serialize_order(first), "order_count": Order.objects.filter(owner=user).count(), "stock_after": Product.objects.get(pk=product.pk).stock}
            else:
                raise ValueError("Operacao nao suportada pelo adaptador fixo.")
            outcome = "passed" if _matches(expected, observed) else "failed"
            transaction.set_rollback(True)
    except BusinessRuleError as exc:
        observed = {"accepted": False, "requirement_id": exc.requirement, "error": str(exc), "order_count": 0, "stock_after": int(inputs.get("stock", 5))}
        outcome = "passed" if _matches(expected, observed) else "failed"
    except Exception as exc:
        observed = {"executor_error": str(exc)}
        outcome = "not_run"
    return {
        "identifier": case["identifier"],
        "requirement_id": case["requirement_id"],
        "revision": case["revision"],
        "inputs": inputs,
        "expected": expected,
        "observed": observed,
        "outcome": outcome,
    }
