from django import forms

from loja.models import Customer


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "email", "city", "notes"]
        labels = {"name": "Nome", "email": "E-mail", "city": "Cidade", "notes": "Observacoes"}


class CheckoutForm(forms.Form):
    customer = forms.ModelChoiceField(queryset=Customer.objects.none(), label="Cliente ficticio")
    idempotency_key = forms.CharField(max_length=64, label="Chave de idempotencia")
    payment_action = forms.ChoiceField(
        choices=[("aprovar", "Aprovar pagamento mock"), ("recusar", "Recusar pagamento mock")],
        label="Resultado deterministico",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["customer"].queryset = Customer.objects.filter(owner=user)

