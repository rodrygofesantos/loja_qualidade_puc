# Guia do professor

Material didático sujeito à revisão do professor. A atividade é aberta, não avaliativa e não foi validada com uma turma; o percurso de 30 minutos é uma estimativa técnica.

## Requisitos e oráculos

| ID | Regra operacional fixada |
|---|---|
| REQ-CAT-001 | Apenas produto ativo entra no carrinho/pedido. |
| REQ-CAR-001 | Quantidade é `int` positivo, excluindo booleano; subtotal soma preço × quantidade em centavos. |
| REQ-CUP-001 | Cupom existe, está ativo e contém o instante no intervalo inclusivo, no fuso da aplicação. |
| REQ-CUP-002 | Percentual inteiro usa `subtotal × valor // 100`; fixo está em centavos; mínimo/teto são aplicados; desconto ≤ subtotal. |
| REQ-EST-001 | Se um item excede estoque, a transação é rejeitada sem pedido confirmado nem consumo; igualdade é aceita. |
| REQ-PED-001 | Checkout recalcula itens persistidos e registra totais coerentes. |
| REQ-PED-002 | Mesma chave e usuário retornam o primeiro pedido; um pedido e um débito. |
| REQ-PAG-001 | Recusa registra pedido recusado sem consumo; aprovação valida e confirma. Não há cartão. |

Arredondamento percentual trunca frações inferiores a um centavo. Ordem: subtotal, validação do cupom, desconto limitado e total não negativo.

## Defeitos e reprodução

| ID | Requisito | Reprodução | Observado defeituoso | Correção |
|---|---|---|---|---|
| BUG-001 | REQ-CUP-001 | `EXPIRADO10`, 15/06/2026 | cupom aceito | validar intervalo com o mesmo relógio |
| BUG-002 | REQ-CUP-002 | `PUC20` sobre 10.000 centavos | desconto 20 centavos | subtotal × percentual ÷ 100 |
| BUG-003 | REQ-EST-001 | seis unidades, estoque cinco | pedido aceito, estoque zerado | atualização condicional; falha aborta transação |
| BUG-004 | REQ-PED-001 | adicionar uma, alterar para duas | total conserva cache de uma | recalcular antes da confirmação |
| BUG-005 | REQ-PED-002 | repetir `MESMA-CHAVE` | dois pedidos e débitos | reservar chave única e retornar pedido |

Os testes `T-CUP-EXPIRADO`, `T-CUP-PERCENTUAL`, `T-EST-LIMITE`, `T-PED-RECALCULO` e `T-PED-IDEMPOTENCIA` usam os mesmos esperados nos dois lados. A suíte de engenharia considera sucesso reproduzir a diferença; o teste didático aparece reprovado no cenário defeituoso.

`T-FRACO-DESCONTO` executa cálculo e verifica apenas `accepted=true`; passa com BUG-002. `T-CUP-PERCENTUAL` confere 2.000 centavos e falha, demonstrando o limite de cobertura e testes superficiais.

## Candidatos e Gate

- `CAND-DEFEITOS`: crítico aberto e falhas conhecidas; `BLOQUEADO`.
- `CAND-CORRIGIDO`: escore baixo e evidências medidas; pode aprovar se critérios atuais forem atendidos.
- `CAND-ALTO-RISCO`: regras corrigidas, perfil extremo e inferência real no/acima de 0,80; continua bloqueado sem sobrescrever score.

`BLOQUEADO` prevalece diante de violação conhecida. `EVIDENCIAS_INSUFICIENTES` indica lacuna sem violação conhecida. `APROVADO` exige todas as regras aplicáveis. Sem correções declaradas é “não aplicável”, nunca prova positiva.

## Restauração

Interface: **Opções da atividade → Reiniciar atividade**, digitando `APAGAR`. Terminal: `python setup_lab.py reset --confirm`. Apenas reiniciar o servidor não restaura dados.
