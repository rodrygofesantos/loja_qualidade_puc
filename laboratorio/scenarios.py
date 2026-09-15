from dataclasses import dataclass


BUGS = {
    "BUG-001": {
        "requirement": "REQ-CUP-001",
        "name": "Cupom vencido aceito",
        "reproduction": "Aplicar EXPIRADO10 no instante fixo de 15/06/2026.",
        "expected": "Cupom rejeitado como vencido.",
        "observed": "O desconto e aplicado apesar do vencimento.",
        "correction": "Validar active, valid_from e valid_until no instante informado.",
    },
    "BUG-002": {
        "requirement": "REQ-CUP-002",
        "name": "Desconto percentual incorreto",
        "reproduction": "Aplicar PUC20 sobre subtotal de R$ 100,00.",
        "expected": "Desconto de R$ 20,00.",
        "observed": "Percentual e tratado como centavos: desconto de R$ 0,20.",
        "correction": "Calcular subtotal * percentual / 100 com aritmetica inteira.",
    },
    "BUG-003": {
        "requirement": "REQ-EST-001",
        "name": "Compra acima do estoque aceita",
        "reproduction": "Comprar seis unidades quando existem cinco.",
        "expected": "Checkout rejeitado sem pedido confirmado ou consumo.",
        "observed": "Pedido confirmado e estoque reduzido ate zero.",
        "correction": "Atualizacao condicional stock__gte dentro de transacao curta.",
    },
    "BUG-004": {
        "requirement": "REQ-PED-001",
        "name": "Total obsoleto apos mudar quantidade",
        "reproduction": "Adicionar uma unidade e alterar para duas antes do checkout.",
        "expected": "Subtotal e total recalculados para duas unidades.",
        "observed": "Checkout conserva o total anterior em cache.",
        "correction": "Recalcular a partir dos itens persistidos antes de confirmar.",
    },
    "BUG-005": {
        "requirement": "REQ-PED-002",
        "name": "Checkout duplicado",
        "reproduction": "Enviar duas vezes a mesma chave de idempotencia.",
        "expected": "Um pedido e um unico efeito no estoque.",
        "observed": "Dois pedidos sao criados e o estoque e debitado duas vezes.",
        "correction": "Reservar chave unica e retornar o pedido associado.",
    },
}


@dataclass(frozen=True)
class ScenarioPolicy:
    code: str
    bugs: frozenset[str]

    def has(self, bug_id):
        return bug_id in self.bugs


def policy_for(scenario):
    bugs = scenario.bug_ids if hasattr(scenario, "bug_ids") else scenario
    code = getattr(scenario, "code", "ad-hoc")
    return ScenarioPolicy(code=code, bugs=frozenset(bugs))

