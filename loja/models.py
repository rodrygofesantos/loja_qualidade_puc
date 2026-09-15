from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    sku = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    price_cents = models.PositiveIntegerField()
    stock = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.CheckConstraint(condition=models.Q(price_cents__gte=0), name="product_price_nonnegative")]

    @property
    def price(self):
        return Decimal(self.price_cents) / 100

    def __str__(self):
        return f"{self.sku} - {self.name}"


class Coupon(models.Model):
    PERCENT = "percent"
    FIXED = "fixed"
    KIND_CHOICES = [(PERCENT, "Percentual"), (FIXED, "Valor fixo")]
    code = models.CharField(max_length=30, unique=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    value = models.PositiveIntegerField(help_text="Percentual inteiro ou centavos")
    max_discount_cents = models.PositiveIntegerField(null=True, blank=True)
    minimum_cents = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.code


class Customer(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customers")
    name = models.CharField(max_length=120)
    email = models.EmailField()
    city = models.CharField(max_length=80)
    notes = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["name"]


class Cart(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    coupon_code = models.CharField(max_length=30, blank=True)
    cached_total_cents = models.PositiveIntegerField(default=0)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="unique_product_per_cart"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="cart_quantity_positive"),
        ]


class Order(models.Model):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REFUSED = "refused"
    STATUS_CHOICES = [(PENDING, "Pendente"), (CONFIRMED, "Confirmado"), (REFUSED, "Recusado")]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    scenario_code = models.CharField(max_length=40)
    code_revision = models.CharField(max_length=40)
    idempotency_key = models.CharField(max_length=64)
    cart_revision = models.PositiveIntegerField()
    subtotal_cents = models.PositiveIntegerField()
    discount_cents = models.PositiveIntegerField(default=0)
    total_cents = models.PositiveIntegerField()
    coupon_code = models.CharField(max_length=30, blank=True)
    payment_result = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class CheckoutAttempt(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    idempotency_key = models.CharField(max_length=64)
    order = models.OneToOneField(Order, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "idempotency_key"], name="unique_checkout_attempt")
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=120)
    unit_price_cents = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()

    @property
    def total_cents(self):
        return self.unit_price_cents * self.quantity
