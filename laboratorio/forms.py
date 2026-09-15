import json

from django import forms

from laboratorio.models import LabReport, TestCase
from laboratorio.test_schema import ALLOWED_OPERATIONS, ALLOWED_REQUIREMENTS, PackageValidationError, validate_package


class TestCaseForm(forms.ModelForm):
    inputs_text = forms.CharField(widget=forms.Textarea(attrs={"rows": 7}), label="Entradas (JSON)")
    expected_text = forms.CharField(widget=forms.Textarea(attrs={"rows": 7}), label="Resultados esperados (JSON)")

    class Meta:
        model = TestCase
        fields = ["identifier", "requirement_id", "description", "scenario_type", "operation", "review_notes"]
        labels = {"identifier": "Identificador", "requirement_id": "Requisito", "description": "Descricao", "scenario_type": "Tipo", "operation": "Operacao", "review_notes": "Notas da revisao humana"}
        widgets = {
            "requirement_id": forms.Select(choices=[(value, value) for value in sorted(ALLOWED_REQUIREMENTS)]),
            "operation": forms.Select(choices=[(value, value) for value in sorted(ALLOWED_OPERATIONS)]),
            "scenario_type": forms.Select(choices=[(value, value) for value in ["relevant_risk", "boundary", "exception", "regression"]]),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        if self.instance.pk:
            self.fields["inputs_text"].initial = json.dumps(self.instance.inputs, ensure_ascii=False, indent=2)
            self.fields["expected_text"].initial = json.dumps(self.instance.expected, ensure_ascii=False, indent=2)

    def clean_identifier(self):
        identifier = self.cleaned_data["identifier"]
        if self.owner is not None:
            duplicate = TestCase.objects.filter(owner=self.owner, identifier=identifier)
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise forms.ValidationError("Este identificador ja existe na sua colecao.")
        return identifier

    def clean_inputs_text(self):
        try:
            value = json.loads(self.cleaned_data["inputs_text"])
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"JSON invalido: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise forms.ValidationError("Entradas devem formar um objeto JSON.")
        return value

    def clean_expected_text(self):
        try:
            value = json.loads(self.cleaned_data["expected_text"])
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"JSON invalido: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise forms.ValidationError("Esperado deve formar um objeto JSON independente.")
        return value

    def clean(self):
        cleaned = super().clean()
        required = ["identifier", "requirement_id", "description", "scenario_type", "operation", "inputs_text", "expected_text"]
        if all(field in cleaned for field in required):
            case = {
                "identifier": cleaned["identifier"], "requirement_id": cleaned["requirement_id"],
                "description": cleaned["description"], "scenario_type": cleaned["scenario_type"],
                "operation": cleaned["operation"], "inputs": cleaned["inputs_text"], "expected": cleaned["expected_text"],
            }
            try:
                validate_package({"schema_version": "1.0", "cases": [case]})
            except PackageValidationError as exc:
                raise forms.ValidationError(str(exc)) from exc
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.inputs = self.cleaned_data["inputs_text"]
        instance.expected = self.cleaned_data["expected_text"]
        instance.reviewed = True
        if instance.pk:
            instance.revision += 1
        if commit:
            instance.save()
        return instance


class ReportForm(forms.ModelForm):
    class Meta:
        model = LabReport
        fields = ["context", "data_decision", "priority", "visualization", "release_decision", "ai_tool", "human_checks"]
        labels = {
            "context": "Contexto",
            "data_decision": "Problema de dados e tratamento",
            "priority": "Prioridade justificada",
            "visualization": "Grafico ou referencia",
            "release_decision": "Decisao de release e pendencias",
            "ai_tool": "Ferramenta de IA utilizada",
            "human_checks": "Verificacoes humanas",
        }
        widgets = {
            "context": forms.Textarea(attrs={"rows": 3}),
            "data_decision": forms.Textarea(attrs={"rows": 3}),
            "priority": forms.Textarea(attrs={"rows": 3}),
            "visualization": forms.Textarea(attrs={"rows": 3}),
            "release_decision": forms.Textarea(attrs={"rows": 3}),
            "human_checks": forms.Textarea(attrs={"rows": 3}),
        }
