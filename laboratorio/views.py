import io
import json
import zipfile
from uuid import uuid4

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from laboratorio.bot import QUESTIONS, answer
from laboratorio.data_pipeline import BASE_DATE, SEED, data_paths, inspect_raw, prepare_data
from laboratorio.executor import execute_cases
from laboratorio.forms import ReportForm, TestCaseForm
from laboratorio.gate import correction_evidence, evaluate_gate
from laboratorio.ml import load_artifact
from laboratorio.models import (
    Candidate,
    DataPreparationRun,
    GateConfig,
    GateEvaluation,
    LabReport,
    ReleaseSimulation,
    RiskPrediction,
    Scenario,
    TestCase,
    TestExecution,
)
from laboratorio.scenarios import BUGS
from laboratorio.test_schema import PackageValidationError, prompt_context, validate_package


def _state(request):
    return request.user.lab_state


@login_required
def overview(request):
    state = _state(request)
    return render(
        request,
        "laboratorio/overview.html",
        {
            "candidate": state.candidate,
            "scenario": state.scenario,
            "test_count": request.user.test_cases.count(),
            "execution_count": request.user.test_executions.count(),
            "latest_gate": GateEvaluation.objects.filter(owner=request.user, candidate=state.candidate).first(),
        },
    )


@login_required
def scenarios(request):
    state = _state(request)
    if request.method == "POST":
        scenario = get_object_or_404(Scenario, pk=request.POST.get("scenario"), active=True)
        candidate = get_object_or_404(Candidate, pk=request.POST.get("candidate"), active=True)
        state.scenario = scenario
        state.candidate = candidate
        state.save(update_fields=["scenario", "candidate", "updated_at"])
        messages.success(request, "Contexto alterado. Evidencias anteriores foram preservadas e nao sao combinadas automaticamente.")
        return redirect("laboratorio:scenarios")
    return render(request, "laboratorio/scenarios.html", {"scenarios": Scenario.objects.filter(active=True), "candidates": Candidate.objects.filter(active=True), "bugs": BUGS})


@login_required
def data_quality(request):
    raw, issues = inspect_raw()
    prepared = None
    if request.method == "POST":
        note = request.POST.get("decision_note", "").strip()
        if len(note) < 10:
            messages.error(request, "Registre uma justificativa de tratamento com pelo menos 10 caracteres.")
        else:
            treated, log = prepare_data(force=False)
            prepared = DataPreparationRun.objects.create(
                run_id=f"DATA-{uuid4().hex}", owner=request.user, seed=SEED, base_date=BASE_DATE,
                raw_rows=log["raw_rows"], treated_rows=log["treated_rows"], issues=log["issues"], transformations=log["transformations"], decision_note=note,
            )
            messages.success(request, f"Preparacao {prepared.run_id} registrada; o bruto foi preservado.")
    treated_preview = []
    treated_path = data_paths()["treated"]
    if treated_path.exists():
        treated_preview = pd.read_csv(treated_path).head(8).fillna("").to_dict("records")
    return render(
        request,
        "laboratorio/data_quality.html",
        {
            "issues": issues,
            "raw_preview": raw.head(8).fillna("").to_dict("records"),
            "treated_preview": treated_preview,
            "prepared": prepared,
            "runs": DataPreparationRun.objects.filter(owner=request.user)[:10],
        },
    )


@login_required
def dashboard(request):
    frame, _ = prepare_data(force=False)
    selected_module = request.GET.get("module", "")
    selected_version = request.GET.get("version", "")
    filtered = frame
    if selected_module:
        filtered = filtered[filtered["module"] == selected_module]
    if selected_version.isdigit():
        filtered = filtered[filtered["version"] == int(selected_version)]
    module_metrics = (
        filtered.groupby("module", as_index=False)
        .agg(churn_lines=("churn_lines", "sum"), commit_frequency=("commit_frequency", "sum"), defects=("defect_next_version", "sum"))
        .sort_values("churn_lines", ascending=False)
        .head(10)
    )
    severity = filtered[filtered["defect_next_version"] == 1]["severity"].value_counts().to_dict()
    latest_execution = request.user.test_executions.filter(status=TestExecution.COMPLETED).first()
    outcomes = {"passed": 0, "failed": 0, "not_run": 0}
    if latest_execution:
        for result in latest_execution.results:
            outcomes[result.get("outcome", "not_run")] = outcomes.get(result.get("outcome", "not_run"), 0) + 1
    chart_data = {
        "modules": module_metrics["module"].tolist(),
        "churn": [int(value) for value in module_metrics["churn_lines"]],
        "frequency": [int(value) for value in module_metrics["commit_frequency"]],
        "defects": [int(value) for value in module_metrics["defects"]],
        "severity": severity,
        "outcomes": outcomes,
    }
    return render(
        request,
        "laboratorio/dashboard.html",
        {
            "chart_data": chart_data,
            "modules": sorted(frame["module"].unique()),
            "versions": sorted(int(value) for value in frame["version"].unique()),
            "selected_module": selected_module,
            "selected_version": selected_version,
            "latest_execution": latest_execution,
            "predictions": RiskPrediction.objects.filter(candidate=_state(request).candidate),
        },
    )


@login_required
def prediction(request):
    error = ""
    metadata = None
    try:
        _, metadata = load_artifact()
    except RuntimeError as exc:
        error = str(exc)
    return render(request, "laboratorio/prediction.html", {"metadata": metadata, "error": error, "predictions": RiskPrediction.objects.filter(candidate=_state(request).candidate), "threshold": GateConfig.objects.first().risk_threshold if GateConfig.objects.exists() else 0.8})


@login_required
def test_cases(request):
    state = _state(request)
    return render(request, "laboratorio/test_cases.html", {"cases": request.user.test_cases.all(), "prompt": prompt_context(state.scenario, state.candidate)})


@login_required
def import_cases(request):
    if request.method == "POST":
        text = request.POST.get("package", "")
        if len(text.encode("utf-8")) > 100_000:
            messages.error(request, "Pacote excede 100 KB.")
        else:
            try:
                package = validate_package(json.loads(text))
                for item in package["cases"]:
                    existing = TestCase.objects.filter(owner=request.user, identifier=item["identifier"]).first()
                    if existing and existing.mandatory:
                        raise PackageValidationError(f"{item['identifier']} e obrigatorio e nao pode ser redefinido pela importacao.")
                    defaults = {
                        "schema_version": package["schema_version"],
                        "requirement_id": item["requirement_id"],
                        "description": item["description"],
                        "scenario_type": item["scenario_type"],
                        "operation": item["operation"],
                        "inputs": item["inputs"],
                        "expected": item["expected"],
                        "mandatory": False,
                        "reviewed": False,
                        "review_notes": "",
                        "revision": (existing.revision + 1) if existing else 1,
                    }
                    TestCase.objects.update_or_create(owner=request.user, identifier=item["identifier"], defaults=defaults)
                messages.success(request, f"{len(package['cases'])} caso(s) importado(s). Revise o esperado antes de executar.")
                return redirect("laboratorio:test_cases")
            except (json.JSONDecodeError, PackageValidationError) as exc:
                messages.error(request, f"Pacote invalido: {exc}")
    example = json.dumps({"schema_version": "1.0", "cases": [{"identifier": "IA-FRONTEIRA-01", "requirement_id": "REQ-EST-001", "description": "Comprar exatamente o estoque", "scenario_type": "boundary", "operation": "check_stock", "inputs": {"stock": 5, "quantity": 5}, "expected": {"accepted": True, "stock_after": 0}}]}, ensure_ascii=False, indent=2)
    return render(request, "laboratorio/import_cases.html", {"example": example})


@login_required
def edit_case(request, pk=None):
    case = get_object_or_404(TestCase, pk=pk, owner=request.user) if pk else None
    if case and case.mandatory:
        messages.error(request, "Casos obrigatorios sao protegidos; crie um caso adicional para experimentar outro oraculo.")
        return redirect("laboratorio:test_cases")
    form = TestCaseForm(request.POST or None, instance=case, owner=request.user)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.owner = request.user
        item.schema_version = "1.0"
        item.mandatory = False
        item.save()
        messages.success(request, "Caso salvo e revisado. A revisao incrementou sua versao.")
        return redirect("laboratorio:test_cases")
    return render(request, "laboratorio/edit_case.html", {"form": form, "case": case})


@login_required
@require_POST
def execute(request):
    selected = request.POST.getlist("cases")
    cases = list(TestCase.objects.filter(owner=request.user, pk__in=selected).order_by("identifier"))
    if not cases:
        messages.error(request, "Selecione ao menos um caso.")
        return redirect("laboratorio:test_cases")
    unreviewed = [case.identifier for case in cases if not case.reviewed]
    if unreviewed:
        messages.error(request, f"Revise antes de executar: {', '.join(unreviewed)}.")
        return redirect("laboratorio:test_cases")
    state = _state(request)
    execution = execute_cases(request.user, state.candidate, state.scenario, cases)
    if execution.status == TestExecution.ERROR:
        messages.error(request, "Erro do executor; nenhum erro foi convertido em teste reprovado.")
    else:
        messages.success(request, f"Execucao {execution.run_id} concluida com cobertura real.")
    return redirect("laboratorio:execution_detail", run_id=execution.run_id)


@login_required
def executions(request):
    return render(request, "laboratorio/executions.html", {"executions": request.user.test_executions.select_related("scenario", "candidate")})


@login_required
def execution_detail(request, run_id):
    execution = get_object_or_404(TestExecution, run_id=run_id, owner=request.user)
    return render(request, "laboratorio/execution_detail.html", {"execution": execution})


@login_required
def coverage(request):
    return render(request, "laboratorio/coverage.html", {"executions": request.user.test_executions.exclude(coverage_percent=None)})


@login_required
def evidence(request):
    candidate = _state(request).candidate
    evidences = [correction_evidence(request.user, candidate, bug_id) for bug_id in candidate.declared_fixes]
    return render(request, "laboratorio/evidence.html", {"candidate": candidate, "evidences": evidences, "bugs": BUGS})


@login_required
def gate(request):
    state = _state(request)
    if request.method == "POST":
        try:
            evaluation = evaluate_gate(request.user, state.candidate)
            message = f"Avaliacao {evaluation.evaluation_id}: {evaluation.status}."
            if evaluation.status == GateEvaluation.BLOCKED:
                messages.error(request, message)
            elif evaluation.status == GateEvaluation.INSUFFICIENT:
                messages.warning(request, message)
            else:
                messages.success(request, message)
        except RuntimeError as exc:
            messages.error(request, str(exc))
        return redirect("laboratorio:gate")
    return render(request, "laboratorio/gate.html", {"evaluations": GateEvaluation.objects.filter(owner=request.user, candidate=state.candidate)[:10], "config": GateConfig.objects.first()})


@login_required
@require_POST
def gate_config(request):
    try:
        coverage_threshold = float(request.POST.get("coverage_threshold", "80"))
        risk_threshold = float(request.POST.get("risk_threshold", "0.8"))
        if not (0 <= coverage_threshold <= 100 and 0 <= risk_threshold <= 1):
            raise ValueError
    except ValueError:
        messages.error(request, "Limiares invalidos: cobertura 0-100; risco 0-1.")
        return redirect("laboratorio:gate")
    previous = GateConfig.objects.first()
    GateConfig.objects.create(version=(previous.version + 1 if previous else 1), coverage_threshold=coverage_threshold, risk_threshold=risk_threshold, note=request.POST.get("note", "Alteracao didatica").strip()[:500], created_by=request.user)
    messages.success(request, "Nova versao de criterios criada; avaliacoes anteriores foram preservadas.")
    return redirect("laboratorio:gate")


@login_required
@require_POST
def release(request):
    state = _state(request)
    shown = get_object_or_404(GateEvaluation, evaluation_id=request.POST.get("evaluation_id"), owner=request.user, candidate=state.candidate)
    newest_config = GateConfig.objects.first()
    if shown.config_id != newest_config.pk or shown.evidence_snapshot.get("candidate_revision") != state.candidate.code_revision:
        messages.error(request, "A avaliacao exibida esta desatualizada. Execute o Gate novamente.")
        return redirect("laboratorio:gate")
    fresh = evaluate_gate(request.user, state.candidate)
    if fresh.status != GateEvaluation.APPROVED:
        messages.error(request, f"Liberacao simulada impedida apos revalidacao: {fresh.status}.")
    else:
        ReleaseSimulation.objects.create(owner=request.user, candidate=state.candidate, evaluation=fresh)
        messages.success(request, f"Release SIMULADA registrada com {fresh.evaluation_id}; nenhuma publicacao externa ocorreu.")
    return redirect("laboratorio:gate")


@login_required
def quality_bot(request):
    state = _state(request)
    action = request.GET.get("action")
    response = answer(request.user, state.candidate, action) if action else "Selecione uma pergunta predefinida."
    return render(request, "laboratorio/bot.html", {"questions": QUESTIONS, "response": response})


def _report_markdown(report, owner):
    executions = owner.test_executions.filter(status=TestExecution.COMPLETED)[:3]
    reviewed_cases = list(owner.test_cases.filter(mandatory=False, reviewed=True).exclude(identifier="T-FRACO-DESCONTO").order_by("-updated_at")[:2])
    case_lines = []
    all_runs = list(owner.test_executions.filter(status=TestExecution.COMPLETED).order_by("-created_at"))
    for case in reviewed_cases:
        matched = None
        matched_run = None
        for run in all_runs:
            matched = next((result for result in run.results if result.get("identifier") == case.identifier and result.get("revision") == case.revision), None)
            if matched:
                matched_run = run
                break
        case_lines.append(
            f"- {case.identifier} v{case.revision} ({case.requirement_id}): "
            + (f"{matched['outcome']} em {matched_run.run_id}; esperado={json.dumps(matched['expected'], ensure_ascii=False)}; observado={json.dumps(matched['observed'], ensure_ascii=False)}" if matched else "revisado, ainda sem resultado compativel")
        )
    return f"""# Relatorio do Laboratorio de Qualidade

## Contexto
{report.context or 'Nao preenchido.'}

## Problema de dados e tratamento
{report.data_decision or 'Nao preenchido.'}

## Prioridade justificada
{report.priority or 'Nao preenchido.'}

## Casos e resultados
{chr(10).join(case_lines) or '- Nenhum dos dois casos adicionais foi revisado.'}

Execucoes recentes:
{chr(10).join(f'- {run.run_id}: {run.status}, cobertura {run.coverage_percent:.2f}%' for run in executions) or '- Nenhuma execucao concluida.'}

## Visualizacao selecionada
{report.visualization or 'Nao preenchido.'}

## Decisao de release e pendencias
{report.release_decision or 'Nao preenchido.'}

## Uso de IA e verificacao humana
Ferramenta: {report.ai_tool or 'Nao informada.'}

{report.human_checks or 'Nao preenchido.'}

## Checklist sem pontuacao
{chr(10).join(f"- [{'x' if value else ' '}] {key.replace('_', ' ')}" for key, value in report.checklist.items())}
"""


@login_required
def report(request):
    item, _ = LabReport.objects.get_or_create(owner=request.user)
    form = ReportForm(request.POST or None, instance=item)
    checklist_keys = ["origem_e_qualidade_dos_dados", "interpretacao_das_metricas", "prioridade", "adequacao_dos_testes", "resultados_e_cobertura", "limites_da_predicao", "evidencias_do_gate", "registro_do_uso_da_ia"]
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.checklist = {key: request.POST.get(key) == "on" for key in checklist_keys}
        item.save()
        messages.success(request, "Relatorio salvo localmente.")
        return redirect("laboratorio:report")
    reviewed_cases = request.user.test_cases.filter(mandatory=False, reviewed=True).exclude(identifier="T-FRACO-DESCONTO").order_by("-updated_at")[:2]
    return render(request, "laboratorio/report.html", {"form": form, "report": item, "checklist_keys": checklist_keys, "reviewed_cases": reviewed_cases})


@login_required
def report_export(request, format):
    report = get_object_or_404(LabReport, owner=request.user)
    markdown = _report_markdown(report, request.user)
    if format == "md":
        response = HttpResponse(markdown, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="relatorio-laboratorio.md"'
        return response
    if format == "html":
        escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return HttpResponse(f"<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>Relatorio</title><style>body{{font:16px system-ui;max-width:850px;margin:40px auto;white-space:pre-wrap}}</style><body>{escaped}</body></html>", content_type="text/html; charset=utf-8")
    return HttpResponse(status=404)


@login_required
def context_export(request):
    state = _state(request)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("contexto.txt", prompt_context(state.scenario, state.candidate))
        archive.writestr("catalogo-dados.md", (settings.BASE_DIR / "docs/DADOS.md").read_text(encoding="utf-8"))
        raw, _ = inspect_raw()
        archive.writestr("amostra-historico-ficticio.csv", raw.head(50).to_csv(index=False))
    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="pacote-contexto-ficticio.zip"'
    return response


@login_required
def schema_download(request):
    schema_path = settings.BASE_DIR / "schemas/test-package-v1.json"
    response = HttpResponse(schema_path.read_text(encoding="utf-8"), content_type="application/schema+json; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="test-package-v1.json"'
    return response


@login_required
def reset(request):
    if request.method == "POST":
        if request.POST.get("confirmation") != "APAGAR":
            messages.error(request, "Digite APAGAR para confirmar a restauracao explicita.")
        else:
            call_command("reset_lab", "--confirm", username=request.user.username)
            messages.success(request, "Progresso local restaurado. Evidencias e pedidos anteriores foram removidos explicitamente.")
            return redirect("laboratorio:overview")
    return render(request, "laboratorio/reset.html")
