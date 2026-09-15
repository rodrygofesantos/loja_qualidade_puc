from laboratorio.models import GateEvaluation, TestExecution


QUESTIONS = {
    "blocked": "Por que a release foi bloqueada?",
    "module": "Qual modulo investigar primeiro?",
    "tests": "Quais testes falharam?",
    "fixes": "Quais correcoes nao tem evidencia?",
    "coverage": "Que limitacoes a cobertura apresenta?",
    "missing": "Quais evidencias faltam?",
}


def answer(owner, candidate, action):
    evaluation = GateEvaluation.objects.filter(owner=owner, candidate=candidate).order_by("-created_at").first()
    if evaluation is None:
        return "Ainda nao existe avaliacao do Gate para este candidato. Execute o Gate; sem ela o bot nao infere motivos."
    rules = {item["rule"]: item for item in evaluation.rule_results}
    if action == "blocked":
        relevant = [f"{item['rule']}: {item['detail']}" for item in evaluation.rule_results if item["status"] in {"fail", "missing"}]
        return f"Estado {evaluation.status} em {evaluation.evaluation_id}. " + (" ".join(relevant) if relevant else "Nenhuma barreira foi registrada.")
    if action == "module":
        scores = evaluation.evidence_snapshot.get("risk_scores", {})
        if not scores:
            return "Nao ha escores compativeis. Prepare o modelo e execute nova avaliacao."
        module, score = max(scores.items(), key=lambda item: item[1])
        return f"Investigue primeiro {module}: maior escore consultado, {score:.6f}, no modelo {evaluation.evidence_snapshot.get('model_version')}. Isto e prioridade estatistica, nao causa comprovada."
    if action == "tests":
        run_id = evaluation.evidence_snapshot.get("execution_run_id")
        execution = TestExecution.objects.filter(run_id=run_id).first() if run_id else None
        if not execution:
            return "Nao ha execucao completa compativel registrada."
        failed = [item["identifier"] for item in execution.results if item.get("outcome") != "passed"]
        return f"Na execucao {run_id}: " + (f"falharam ou nao rodaram {', '.join(failed)}." if failed else "todos os casos registrados passaram.")
    if action == "fixes":
        return rules.get("Correcoes declaradas", {"detail": "Regra nao calculada."})["detail"]
    if action == "coverage":
        detail = rules.get("Cobertura", {"detail": "Cobertura ausente."})["detail"]
        return f"{detail} Cobertura indica linhas executadas, nao qualidade do oraculo; compare T-FRACO-DESCONTO com T-CUP-PERCENTUAL."
    if action == "missing":
        missing = [f"{item['rule']}: {item['detail']}" for item in evaluation.rule_results if item["status"] == "missing"]
        return " ".join(missing) if missing else "Nenhuma evidencia ausente foi registrada nesta avaliacao."
    return "Acao desconhecida. O bot aceita apenas as perguntas predefinidas exibidas na tela."

