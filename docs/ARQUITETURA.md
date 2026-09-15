# Arquitetura e decisões técnicas

`config` contém infraestrutura Django. `loja` concentra persistência comercial, domínio puro (`domain.py`) e serviços transacionais (`services.py`). `laboratorio` concentra políticas de cenário, geração/preparação, ML, contrato de casos, adaptadores, executor isolado, Gate, bot e apresentação.

```text
interface da loja ─┐
executor isolado ──┼─> loja.domain + loja.services ─> SQLite
dados sintéticos -> preparação pandas -> pipeline sklearn -> inferências
casos + cobertura + inferências + vínculos -> Gate determinístico -> bot de leitura
```

## SQLite e checkout

SQLite não implementa bloqueio de linha por `SELECT FOR UPDATE`. A conexão usa transação `IMMEDIATE`, timeout e blocos `transaction.atomic()` curtos. Não há rede, subprocesso ou ML dentro da transação comercial.

Na referência corrigida, débito usa `filter(stock__gte=quantidade).update(stock=F('stock')-quantidade)`. Se não atualizar uma linha, a exceção aborta pedido e débitos. Idempotência usa `CheckoutAttempt` com unicidade `(owner, idempotency_key)`; BUG-005 ignora deliberadamente essa reserva sem enfraquecer a referência.

## Estado e evidências

Preços são centavos; datas são timezone-aware. Testes usam 15/06/2026 12:00. Cenário é salvo por usuário; pedido e execução copiam cenário/revisão, evitando variável global. Execuções carregam candidato, revisão do código/casos e horário. O Gate aceita apenas execução completa compatível. Inferências carregam modelo e atributos.

O JSON nunca escolhe função, módulo, caminho ou comando. O processo pai cria diretório UUID, chama lista fixa com `shell=False`, timeout e SQLite temporário; o filho usa adaptadores fixos e os mesmos serviços da loja.

## Separação conceitual

- regressão logística produz escore sintético;
- bot de regras resume avaliação existente;
- IA externa opcional propõe JSON sujeito a revisão;
- Gate decide deterministicamente e não pode ser sobreposto pelos demais.

