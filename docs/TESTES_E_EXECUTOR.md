# Casos, schema e executor

## Contrato 1.0

O arquivo [test-package-v1.json](../schemas/test-package-v1.json) documenta o JSON Schema. Pacote: `schema_version` e `cases` (1–10; o exercício solicita exatamente dois). Cada caso contém:

- `identifier`: ID alfanumérico com hífen/sublinhado, até 60 caracteres;
- `requirement_id`: um dos oito requisitos;
- `description`;
- `scenario_type`: `relevant_risk`, `boundary`, `exception`, `regression` ou `mandatory`;
- `operation`: enum fechado;
- `inputs`: objeto com dados fictícios;
- `expected`: objeto independente com as propriedades essenciais esperadas.

Operações: `calculate_cart`, `apply_coupon`, `check_stock`, `checkout`, `payment`, `repeat_checkout`. Exemplos inválidos: `operation: "run_python"`, ausência de `expected`, requisito desconhecido, lista acima de 10 ou texto acima de 100 KB.

```json
{
  "schema_version": "1.0",
  "cases": [{
    "identifier": "IA-ESTOQUE-LIMITE",
    "requirement_id": "REQ-EST-001",
    "description": "Compra exatamente todo o estoque",
    "scenario_type": "boundary",
    "operation": "check_stock",
    "inputs": {"stock": 5, "quantity": 5},
    "expected": {"accepted": true, "stock_after": 0}
  }]
}
```

## Revisão e isolamento

Importação deixa o caso pendente. O aluno precisa revisar requisito e oráculo; salvar incrementa a revisão. Casos obrigatórios são protegidos. Resultado é aprovado apenas se todas as chaves do esperado forem iguais às observadas; o esperado nunca é preenchido pelo observado.

Uma execução cria diretório UUID, entrada imutável e SQLite temporário. Subprocesso usa o interpretador da `.venv`, lista fixa, `shell=False`, timeout de 30 s e adaptadores fixos. Cada caso roda em transação revertida. O processo fecha conexões e remove banco/WAL/journal, inclusive no Windows. `waiting`, `running`, `completed` e `error` descrevem infraestrutura; dentro de `completed`, cada caso é `passed`, `failed` ou `not_run`.

O mesmo subprocesso é medido com coverage.py no escopo estável `loja.domain, loja.services`, gerando JSON e HTML próprios. Seleção parcial permanece `selection`; só conjunto contendo todos os obrigatórios é `full` e pode alimentar o Gate.

