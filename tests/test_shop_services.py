from datetime import datetime
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from loja.domain import BusinessRuleError
from loja.models import Category, Customer, Order, Product
from loja.services import add_to_cart, checkout, get_cart


@pytest.fixture
def shop(db):
    user = get_user_model().objects.create_user("service-user", password="x")
    category = Category.objects.create(name="Teste", slug="teste")
    product = Product.objects.create(sku="TEST-1", name="Produto", description="Ficticio", category=category, price_cents=1250, stock=5)
    customer = Customer.objects.create(owner=user, name="Cliente", email="c@example.invalid", city="Recife")
    return user, product, customer


def corrected():
    return SimpleNamespace(code="corrigido", bug_ids=[])


@pytest.mark.django_db
@pytest.mark.engenharia
def test_corrected_checkout_is_idempotent_and_debits_once(shop):
    user, product, customer = shop
    add_to_cart(user, product, 2, corrected())
    first, first_created = checkout(user, customer, corrected(), "KEY-1", "aprovar")
    second, second_created = checkout(user, customer, corrected(), "KEY-1", "aprovar")
    product.refresh_from_db()
    assert first_created is True
    assert second_created is False
    assert first.pk == second.pk
    assert Order.objects.filter(owner=user).count() == 1
    assert product.stock == 3
    assert first.total_cents == 2500


@pytest.mark.django_db
@pytest.mark.engenharia
def test_refused_payment_does_not_consume_stock(shop):
    user, product, customer = shop
    add_to_cart(user, product, 2, corrected())
    order, _ = checkout(user, customer, corrected(), "KEY-REFUSE", "recusar")
    product.refresh_from_db()
    assert order.status == Order.REFUSED
    assert product.stock == 5


@pytest.mark.django_db
@pytest.mark.engenharia
def test_stock_failure_rolls_back_order_and_stock(shop):
    user, product, customer = shop
    add_to_cart(user, product, 6, corrected())
    with pytest.raises(BusinessRuleError) as error:
        checkout(user, customer, corrected(), "KEY-STOCK", "aprovar")
    product.refresh_from_db()
    assert error.value.requirement == "REQ-EST-001"
    assert Order.objects.filter(owner=user).count() == 0
    assert product.stock == 5


@pytest.mark.django_db
@pytest.mark.engenharia
def test_inactive_product_is_rejected(shop):
    user, product, _ = shop
    product.active = False
    product.save()
    with pytest.raises(BusinessRuleError) as error:
        add_to_cart(user, product, 1, corrected())
    assert error.value.requirement == "REQ-CAT-001"
    assert get_cart(user).items.count() == 0

