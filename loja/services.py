from dataclasses import asdict
from uuid import uuid4

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from laboratorio.scenarios import policy_for
from loja.domain import BusinessRuleError, CouponData, calculate_totals
from loja.models import Cart, CartItem, CheckoutAttempt, Coupon, Order, OrderItem, Product


def get_cart(user):
    cart, _ = Cart.objects.get_or_create(owner=user)
    return cart


def _coupon_data(code):
    if not code:
        return None
    try:
        coupon = Coupon.objects.get(code__iexact=code)
    except Coupon.DoesNotExist as exc:
        raise BusinessRuleError("REQ-CUP-001", "Cupom inexistente.") from exc
    return CouponData(
        code=coupon.code,
        kind=coupon.kind,
        value=coupon.value,
        minimum_cents=coupon.minimum_cents,
        max_discount_cents=coupon.max_discount_cents,
        active=coupon.active,
        valid_from=coupon.valid_from,
        valid_until=coupon.valid_until,
    )


def cart_items_payload(cart):
    return [
        {"sku": item.product.sku, "unit_price_cents": item.product.price_cents, "quantity": item.quantity}
        for item in cart.items.select_related("product").all()
    ]


def summarize_cart(cart, scenario, now=None, checkout=False):
    now = now or timezone.now()
    policy = policy_for(scenario)
    totals = calculate_totals(cart_items_payload(cart), _coupon_data(cart.coupon_code), now, policy)
    if policy.has("BUG-004") and checkout and cart.cached_total_cents:
        totals["total_cents"] = cart.cached_total_cents
    return totals


def add_to_cart(user, product, quantity, scenario):
    if not product.active:
        raise BusinessRuleError("REQ-CAT-001", "Produto inativo nao pode ser adicionado.")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise BusinessRuleError("REQ-CAR-001", "Quantidade deve ser inteira e positiva.")
    cart = get_cart(user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": quantity})
    if not created:
        item.quantity = F("quantity") + quantity
        item.save(update_fields=["quantity"])
        item.refresh_from_db()
    cart.revision = F("revision") + 1
    cart.save(update_fields=["revision", "updated_at"])
    cart.refresh_from_db()
    totals = summarize_cart(cart, scenario)
    cart.cached_total_cents = totals["total_cents"]
    cart.save(update_fields=["cached_total_cents"])
    return item


def update_cart_item(item, quantity, scenario):
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise BusinessRuleError("REQ-CAR-001", "Quantidade deve ser inteira e positiva.")
    cart = item.cart
    item.quantity = quantity
    item.save(update_fields=["quantity"])
    cart.revision = F("revision") + 1
    cart.save(update_fields=["revision", "updated_at"])
    cart.refresh_from_db()
    if not policy_for(scenario).has("BUG-004"):
        cart.cached_total_cents = summarize_cart(cart, scenario)["total_cents"]
        cart.save(update_fields=["cached_total_cents"])


def apply_coupon(cart, code, scenario, now=None):
    normalized = code.strip().upper()
    coupon = _coupon_data(normalized)
    calculate_totals(cart_items_payload(cart), coupon, now or timezone.now(), policy_for(scenario))
    cart.coupon_code = normalized
    cart.revision = F("revision") + 1
    cart.save(update_fields=["coupon_code", "revision", "updated_at"])
    cart.refresh_from_db()
    cart.cached_total_cents = summarize_cart(cart, scenario, now)["total_cents"]
    cart.save(update_fields=["cached_total_cents"])


def checkout(user, customer, scenario, idempotency_key, payment_action, now=None):
    key = idempotency_key.strip()
    if not key or len(key) > 64:
        raise BusinessRuleError("REQ-PED-002", "Chave de idempotencia obrigatoria (ate 64 caracteres).")
    policy = policy_for(scenario)
    with transaction.atomic():
        if not policy.has("BUG-005"):
            attempt, created = CheckoutAttempt.objects.get_or_create(owner=user, idempotency_key=key)
            if not created and attempt.order_id:
                return attempt.order, False
        else:
            attempt = None

        cart = Cart.objects.get(owner=user)
        items = list(cart.items.select_related("product"))
        if not items:
            raise BusinessRuleError("REQ-CAR-001", "O carrinho esta vazio.")
        totals = summarize_cart(cart, scenario, now=now, checkout=True)
        approved = payment_action == "aprovar"
        status = Order.CONFIRMED if approved else Order.REFUSED
        order = Order.objects.create(
            owner=user,
            customer=customer,
            scenario_code=scenario.code,
            code_revision=settings.LAB_REVISION,
            idempotency_key=key,
            cart_revision=cart.revision,
            coupon_code=cart.coupon_code,
            payment_result="approved" if approved else "refused",
            status=status,
            **totals,
        )
        OrderItem.objects.bulk_create([
            OrderItem(
                order=order,
                product=item.product,
                product_name=item.product.name,
                unit_price_cents=item.product.price_cents,
                quantity=item.quantity,
            ) for item in items
        ])
        if approved:
            for item in items:
                if policy.has("BUG-003"):
                    Product.objects.filter(pk=item.product_id).update(stock=0 if item.quantity > item.product.stock else F("stock") - item.quantity)
                    continue
                changed = Product.objects.filter(pk=item.product_id, stock__gte=item.quantity).update(stock=F("stock") - item.quantity)
                if changed != 1:
                    raise BusinessRuleError("REQ-EST-001", f"Estoque insuficiente para {item.product.sku}.")
        if attempt is not None:
            attempt.order = order
            attempt.save(update_fields=["order"])
        return order, True


def serialize_order(order):
    return {
        "order_id": order.pk,
        "status": order.status,
        "subtotal_cents": order.subtotal_cents,
        "discount_cents": order.discount_cents,
        "total_cents": order.total_cents,
        "payment_result": order.payment_result,
    }

