from django.urls import path

from laboratorio import views


app_name = "laboratorio"
urlpatterns = [
    path("", views.overview, name="overview"),
    path("cenarios/", views.scenarios, name="scenarios"),
    path("dados/", views.data_quality, name="data_quality"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("predicao/", views.prediction, name="prediction"),
    path("testes/", views.test_cases, name="test_cases"),
    path("testes/importar/", views.import_cases, name="import_cases"),
    path("testes/novo/", views.edit_case, name="new_case"),
    path("testes/<int:pk>/", views.edit_case, name="edit_case"),
    path("testes/executar/", views.execute, name="execute"),
    path("execucoes/", views.executions, name="executions"),
    path("execucoes/<str:run_id>/", views.execution_detail, name="execution_detail"),
    path("cobertura/", views.coverage, name="coverage"),
    path("evidencias/", views.evidence, name="evidence"),
    path("gate/", views.gate, name="gate"),
    path("gate/configuracao/", views.gate_config, name="gate_config"),
    path("gate/liberar/", views.release, name="release"),
    path("bot/", views.quality_bot, name="bot"),
    path("relatorio/", views.report, name="report"),
    path("relatorio/exportar/<str:format>/", views.report_export, name="report_export"),
    path("exportar-contexto/", views.context_export, name="context_export"),
    path("schema/test-package-v1.json", views.schema_download, name="schema_download"),
    path("restaurar/", views.reset, name="reset"),
]
