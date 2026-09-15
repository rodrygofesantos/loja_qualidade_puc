from django.urls import path

from loja import views


app_name = "loja"
urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("produto/<int:pk>/", views.product_detail, name="product_detail"),
    path("produto/<int:pk>/adicionar/", views.cart_add, name="cart_add"),
    path("carrinho/", views.cart_view, name="cart"),
    path("carrinho/item/<int:item_id>/atualizar/", views.cart_update, name="cart_update"),
    path("carrinho/item/<int:item_id>/remover/", views.cart_remove, name="cart_remove"),
    path("carrinho/cupom/", views.coupon_apply, name="coupon_apply"),
    path("checkout/", views.checkout_view, name="checkout"),
    path("clientes/", views.customers, name="customers"),
    path("clientes/novo/", views.customer_edit, name="customer_new"),
    path("clientes/<int:pk>/", views.customer_edit, name="customer_edit"),
    path("pedidos/", views.orders, name="orders"),
    path("pedidos/<int:pk>/", views.order_detail, name="order_detail"),
]

