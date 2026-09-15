from dataclasses import dataclass
from datetime import datetime


class BusinessRuleError(ValueError):
    def __init__(self, requirement, message):
        self.requirement = requirement
        super().__init__(message)


@dataclass(frozen=True)
class CouponData:
    code: str
    kind: str
    value: int
    minimum_cents: int
    max_discount_cents: int | None
    active: bool
    valid_from: datetime
    valid_until: datetime


def subtotal_cents(items):
    total = 0
    for item in items:
        quantity = item["quantity"]
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise BusinessRuleError("REQ-CAR-001", "A quantidade deve ser um inteiro positivo.")
        price = item["unit_price_cents"]
        if isinstance(price, bool) or not isinstance(price, int) or price < 0:
            raise BusinessRuleError("REQ-CAR-001", "Preco em centavos invalido.")
        total += price * quantity
    return total


def coupon_discount(subtotal, coupon, now, policy):
    if coupon is None:
        return 0
    if not coupon.active:
        raise BusinessRuleError("REQ-CUP-001", "Cupom inativo.")
    if not policy.has("BUG-001") and not (coupon.valid_from <= now <= coupon.valid_until):
        raise BusinessRuleError("REQ-CUP-001", "Cupom fora da validade.")
    if subtotal < coupon.minimum_cents:
        raise BusinessRuleError("REQ-CUP-002", "Subtotal abaixo do minimo do cupom.")
    if coupon.kind == "percent":
        if not 0 <= coupon.value <= 100:
            raise BusinessRuleError("REQ-CUP-002", "Percentual de cupom invalido.")
        discount = coupon.value if policy.has("BUG-002") else subtotal * coupon.value // 100
    elif coupon.kind == "fixed":
        discount = coupon.value
    else:
        raise BusinessRuleError("REQ-CUP-002", "Tipo de cupom invalido.")
    if coupon.max_discount_cents is not None:
        discount = min(discount, coupon.max_discount_cents)
    return min(subtotal, discount)


def calculate_totals(items, coupon, now, policy):
    subtotal = subtotal_cents(items)
    discount = coupon_discount(subtotal, coupon, now, policy)
    return {"subtotal_cents": subtotal, "discount_cents": discount, "total_cents": subtotal - discount}

