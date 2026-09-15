# Modelo preditivo local

## Objetivo e corte

Regressão logística estima um **escore de risco** de um módulo apresentar defeito na próxima versão. O conjunto tem aproximadamente 1.000 observações sintéticas. Isso ilustra o processo, não valida uso em produção.

Para uma linha da versão `v`, `churn_lines`, `commit_frequency`, `size_loc` e `previous_defects` existem no fechamento de `v`; `defect_next_version` só é conhecido em `v+1`. O corte de dados é 21. Linhas cujo rótulo ainda não estaria disponível são excluídas.

- treino: versões 1–14, todos os módulos juntos;
- validação: 15–17;
- teste final intocado: 18–20;
- semente: 20260615.

Não há embaralhamento entre versões. Imputação de mediana, padronização e regressão são ajustadas somente no treino por `sklearn.pipeline.Pipeline`. Um `DummyClassifier(most_frequent)` é a comparação de baseline. O teste final não seleciona limiar, cenário ou hiperparâmetro.

## Artefato e reprodução

```bash
.venv/bin/python manage.py train_risk_model --force
```

O pipeline fica em `artifacts/model/risk_pipeline.joblib`; versão, bibliotecas, atributos, cortes, matriz de confusão, precisão, recall, F1 e limitações ficam em `metadata.json`. Ambos são locais e reconstruíveis. A aplicação carrega o modelo uma vez por inferência, nunca treina em requisição.

Artefato ausente, corrompido ou com metadados incompatíveis gera erro explícito e `EVIDENCIAS_INSUFICIENTES`; não há score substituto.

## Interpretação

O escore bruto, sem arredondamento, é comparado ao limiar: `score >= 0.80` bloqueia. A tela pode arredondar apenas a apresentação. Explicações são `atributo_padronizado × coeficiente` na escala de log-odds do modelo linear. Não são causas.

Passar um teste ou corrigir um defeito não muda score. Somente novo vetor de atributos válido ou nova versão do modelo cria nova inferência. Status do cenário, resultado do Gate, identificadores e dados futuros não entram nas features.

## Limitações

Os dados são sintéticos, relações são simuladas, o escore não é uma probabilidade calibrada de produção, não há garantia de desempenho mínimo e importância/contribuição não prova causalidade. Os candidatos demonstrativos são externos ao teste final; seus scores são inferências reais, nunca cores ou valores sobrescritos.

