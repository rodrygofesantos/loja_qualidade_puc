from django.conf import settings
from django.db import models


class Scenario(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField()
    bug_ids = models.JSONField(default=list)
    revision = models.CharField(max_length=30, default="scenario-v1")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.name


class Candidate(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField()
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT)
    changed_modules = models.JSONField(default=list)
    open_critical_defects = models.JSONField(default=list)
    declared_fixes = models.JSONField(default=list)
    code_revision = models.CharField(max_length=40, default="lab-v1")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]


class UserLabState(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lab_state")
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT)
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)


class TestCase(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="test_cases")
    identifier = models.CharField(max_length=60)
    schema_version = models.CharField(max_length=10, default="1.0")
    revision = models.PositiveIntegerField(default=1)
    requirement_id = models.CharField(max_length=30)
    description = models.CharField(max_length=240)
    scenario_type = models.CharField(max_length=30)
    operation = models.CharField(max_length=40)
    inputs = models.JSONField(default=dict)
    expected = models.JSONField(default=dict)
    mandatory = models.BooleanField(default=False)
    reviewed = models.BooleanField(default=False)
    review_notes = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["identifier"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "identifier"], name="unique_test_identifier_per_owner")
        ]


class TestExecution(models.Model):
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    STATUS_CHOICES = [
        (WAITING, "Aguardando"),
        (RUNNING, "Em execucao"),
        (COMPLETED, "Concluida"),
        (ERROR, "Erro do executor"),
    ]
    run_id = models.CharField(max_length=64, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="test_executions")
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT)
    scenario_revision = models.CharField(max_length=30, default="scenario-v1")
    code_revision = models.CharField(max_length=40)
    case_revisions = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=WAITING)
    results = models.JSONField(default=list)
    coverage_lines = models.PositiveIntegerField(null=True, blank=True)
    coverage_considered = models.PositiveIntegerField(null=True, blank=True)
    coverage_percent = models.FloatField(null=True, blank=True)
    coverage_scope = models.CharField(max_length=120, default="loja.domain, loja.services")
    scope_kind = models.CharField(max_length=20, default="selection")
    error_message = models.TextField(blank=True)
    artifact_dir = models.CharField(max_length=300, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class DataPreparationRun(models.Model):
    run_id = models.CharField(max_length=64, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    seed = models.PositiveIntegerField()
    base_date = models.DateField()
    raw_rows = models.PositiveIntegerField()
    treated_rows = models.PositiveIntegerField()
    issues = models.JSONField(default=dict)
    transformations = models.JSONField(default=list)
    decision_note = models.CharField(max_length=800)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class RiskPrediction(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="predictions")
    module = models.CharField(max_length=80)
    model_version = models.CharField(max_length=40)
    features = models.JSONField(default=dict)
    score = models.FloatField()
    explanation = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["candidate", "module", "model_version"], name="unique_candidate_prediction")
        ]


class GateConfig(models.Model):
    version = models.PositiveIntegerField(unique=True)
    coverage_threshold = models.FloatField(default=80.0)
    risk_threshold = models.FloatField(default=0.8)
    note = models.CharField(max_length=500)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]


class GateEvaluation(models.Model):
    APPROVED = "APROVADO"
    BLOCKED = "BLOQUEADO"
    INSUFFICIENT = "EVIDENCIAS_INSUFICIENTES"
    evaluation_id = models.CharField(max_length=64, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT)
    config = models.ForeignKey(GateConfig, on_delete=models.PROTECT)
    status = models.CharField(max_length=30)
    rule_results = models.JSONField(default=list)
    evidence_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ReleaseSimulation(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT)
    evaluation = models.ForeignKey(GateEvaluation, on_delete=models.PROTECT)
    released_at = models.DateTimeField(auto_now_add=True)


class LabReport(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    context = models.TextField(blank=True)
    data_decision = models.TextField(blank=True)
    priority = models.TextField(blank=True)
    visualization = models.TextField(blank=True)
    release_decision = models.TextField(blank=True)
    ai_tool = models.CharField(max_length=120, blank=True)
    human_checks = models.TextField(blank=True)
    checklist = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)
