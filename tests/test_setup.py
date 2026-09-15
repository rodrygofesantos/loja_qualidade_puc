import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from laboratorio.models import LabReport
from loja.models import Product


@pytest.mark.django_db
@pytest.mark.engenharia
def test_seed_is_idempotent_and_preserves_progress(demo_user):
    product = Product.objects.get(sku="SKU-CAFE")
    product.stock = 2
    product.save(update_fields=["stock"])
    report = LabReport.objects.get(owner=demo_user)
    report.context = "Meu progresso"
    report.save()
    call_command("seed_demo", verbosity=0)
    assert Product.objects.get(sku="SKU-CAFE").stock == 2
    assert LabReport.objects.get(owner=demo_user).context == "Meu progresso"


@pytest.mark.django_db
@pytest.mark.engenharia
def test_reset_requires_confirmation_and_explicitly_restores_progress(demo_user):
    report = LabReport.objects.get(owner=demo_user)
    report.context = "sera removido"
    report.save()
    product = Product.objects.get(sku="SKU-CAFE")
    product.stock = 1
    product.save(update_fields=["stock"])
    with pytest.raises(CommandError, match="--confirm"):
        call_command("reset_lab")
    assert LabReport.objects.get(owner=demo_user).context == "sera removido"
    call_command("reset_lab", "--confirm", verbosity=0)
    assert LabReport.objects.get(owner=demo_user).context == ""
    assert Product.objects.get(sku="SKU-CAFE").stock == 5
