# Catálogo de dados, limpeza e métricas

Todo histórico é sintético: seed `20260615`, data-base `2026-06-15`, 50 módulos × 20 versões = 1.000 observações tratadas. IDs `SIM-*` não são commits Git.

## `module_versions.csv`

Unidade: módulo no fechamento da versão. Período fictício: versões 1–20. Origem: gerador local.

| Campo | Significado |
|---|---|
| `record_id` | ID `SIM-MV-*`; duplicidades brutas repetem o ID. |
| `module`, `version` | módulo fictício e janela ordinal. |
| `feature_available_version` | quando atributos já existem. |
| `label_available_version` | versão seguinte, quando resultado vira conhecido. |
| `churn_lines` | linhas adicionadas + removidas. |
| `commit_frequency` | commits simulados distintos. |
| `size_loc` | tamanho no fechamento, em linhas. |
| `previous_defects` | defeitos conhecidos antes do próximo resultado. |
| `defect_next_version` | rótulo binário sintético, nunca imputado. |
| `defect_id`, `severity` | vínculo e severidade fictícios. |
| `declared_fix`, `linked_test` | declaração e vínculo alegado; não comprovam correção. |
| `source` | `historico_sintetico`. |

`change_events.csv` tem unidade por alteração: `change_id`, módulo, versão, commit, linhas adicionadas/removidas. Resultados atuais vivem em `TestExecution`, `DataPreparationRun`, `RiskPrediction` e `GateEvaluation`, separados do histórico.

## Problemas e tratamento

Há 10 IDs duplicados, 12 churns ausentes, 6 vínculos `SIM-DEF-INEXISTENTE`, declarações sem teste e 8 eventos duplicados. O tratamento deduplica pelo ID, imputa apenas churn pela mediana do módulo (fallback global), nunca imputa rótulo, marca vínculos incoerentes sem descartá-los e só deriva `fix_verified` com declaração, teste e vínculo coerente.

`churn = Σ(adicionadas + removidas)` após deduplicar `change_id`. `frequência = count(distinct commit_id)`. Churn não é perda de clientes; frequência não é volume; defeitos são contagem, não densidade.

