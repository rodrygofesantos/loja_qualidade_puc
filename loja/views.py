from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from loja.domain import BusinessRuleError
from loja.forms import CheckoutForm, CustomerForm
from loja.models import CartItem, Category, Customer, Order, Product
from loja.services import add_to_cart, apply_coupon, checkout, get_cart, summarize_cart, update_cart_item


def _scenario(request):
    try:
        return request.user.lab_state.scenario
    except AttributeError as exc:
        raise Http404("Execute a preparacao inicial do laboratorio.") from exc


@login_required
def catalog(request):
    products = Product.objects.filter(active=True).select_related("category")
    query = request.GET.get("q", "").strip()
    category = request.GET.get("categoria", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(sku__icontains=query))
    if category:
        products = products.filter(category__slug=category)
    return render(request, "loja/catalog.html", {"products": products, "categories": Category.objects.all(), "query": query, "selected_category": category})


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related("category"), pk=pk)
    return render(request, "loja/product_detail.html", {"product": product})


@login_required
@require_POST
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    try:
        quantity = int(request.POST.get("quantity", "1"))
        add_to_cart(request.user, product, quantity, _scenario(request))
        messages.success(request, f"{product.name} foi adicionado ao carrinho.")
    except (ValueError, BusinessRuleError) as exc:
        messages.error(request, str(exc))
    return redirect("loja:cart")


@login_required
def cart_view(request):
    cart = get_cart(request.user)
    try:
        totals = summarize_cart(cart, _scenario(request))
        error = ""
    except BusinessRuleError as exc:
        totals = {"subtotal_cents": 0, "discount_cents": 0, "total_cents": 0}
        error = str(exc)
    return render(request, "loja/cart.html", {"cart": cart, "totals": totals, "cart_error": error})


@login_required
@require_POST
def cart_update(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__owner=request.user)
    try:
        update_cart_item(item, int(request.POST.get("quantity", "0")), _scenario(request))
        messages.success(request, "Quantidade atualizada.")
    except (ValueError, BusinessRuleError) as exc:
        messages.error(request, str(exc))
    return redirect("loja:cart")


@login_required
@require_POST
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__owner=request.user)
    cart = item.cart
    item.delete()
    cart.revision += 1
    cart.save(update_fields=["revision", "updated_at"])
    messages.success(request, "Item removido.")
    return redirect("loja:cart")


@login_required
@require_POST
def coupon_apply(request):
    cart = get_cart(request.user)
    try:
        apply_coupon(cart, request.POST.get("code", ""), _scenario(request))
        messages.success(request, "Cupom aplicado conforme o cenario ativo.")
    except BusinessRuleError as exc:
        messages.error(request, f"{exc.requirement}: {exc}")
    return redirect("loja:cart")


@login_required
def checkout_view(request):
    cart = get_cart(request.user)
    scenario = _scenario(request)
    initial = {"idempotency_key": f"LAB-{uuid4().hex[:12].upper()}"}
    form = CheckoutForm(request.POST or None, user=request.user, initial=initial)
    try:
        totals = summarize_cart(cart, scenario, checkout=True)
    except BusinessRuleError as exc:
        totals = None
        messages.error(request, f"{exc.requirement}: {exc}")
    if request.method == "POST" and form.is_valid():
        try:
            order, created = checkout(
                request.user,
                form.cleaned_data["customer"],
                scenario,
                form.cleaned_data["idempotency_key"],
                form.cleaned_data["payment_action"],
            )
            messages.success(request, "Pedido criado." if created else "Repeticao detectada: o pedido existente foi retornado.")
            return redirect("loja:order_detail", pk=order.pk)
        except BusinessRuleError as exc:
            messages.error(request, f"{exc.requirement}: {exc}")
    return render(request, "loja/checkout.html", {"form": form, "cart": cart, "totals": totals})


@login_required
def customers(request):
    return render(request, "loja/customers.html", {"customers": Customer.objects.filter(owner=request.user)})


@login_required
def customer_edit(request, pk=None):
    instance = get_object_or_404(Customer, pk=pk, owner=request.user) if pk else None
    form = CustomerForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        customer = form.save(commit=False)
        customer.owner = request.user
        customer.save()
        messages.success(request, "Cliente ficticio salvo.")
        return redirect("loja:customers")
    return render(request, "loja/customer_form.html", {"form": form, "customer": instance})


@login_required
def orders(request):
    return render(request, "loja/orders.html", {"orders": Order.objects.filter(owner=request.user).select_related("customer")})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk, owner=request.user)
    return render(request, "loja/order_detail.html", {"order": order})

