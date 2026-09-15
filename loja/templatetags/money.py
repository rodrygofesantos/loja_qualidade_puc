from decimal import Decimal

from django import template


register = template.Library()


@register.filter
def brl_cents(value):
    try:
        amount = Decimal(int(value)) / 100
    except (ValueError, TypeError):
        return "R$ --"
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"

