from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from laboratorio.models import DataPreparationRun, GateEvaluation, LabReport, ReleaseSimulation, TestCase, TestExecution, UserLabState
from loja.models import Cart, CheckoutAttempt, Coupon, Customer, Order, Product


class Command(BaseCommand):
    help = "Restaura explicitamente o progresso da conta demonstrativa."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--username", default="aluno")

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Operacao destrutiva: repita com --confirm.")
        user = get_user_model().objects.filter(username=options["username"]).first()
        if user is None:
            raise CommandError("Usuario informado nao existe.")
        with transaction.atomic():
            ReleaseSimulation.objects.filter(owner=user).delete()
            GateEvaluation.objects.filter(owner=user).delete()
            TestExecution.objects.filter(owner=user).delete()
            DataPreparationRun.objects.filter(owner=user).delete()
            LabReport.objects.filter(owner=user).delete()
            TestCase.objects.filter(owner=user).delete()
            UserLabState.objects.filter(user=user).delete()
            Order.objects.filter(owner=user).delete()
            CheckoutAttempt.objects.filter(owner=user).delete()
            Cart.objects.filter(owner=user).delete()
            Customer.objects.filter(owner=user).delete()
            Product.objects.all().delete()
            Coupon.objects.all().delete()
        call_command("seed_demo")
        self.stdout.write(self.style.SUCCESS(f"Progresso de {user.username} restaurado."))
