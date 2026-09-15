# Guia do aluno — atividade aberta de 30 minutos

## Desafio

Você recebeu uma loja pronta e deve recomendar ou bloquear uma release **simulada**. Não há nota nem uma única conclusão textual correta; a decisão precisa respeitar os requisitos e as evidências. Não edite Python, não configure API e não treine o modelo durante a atividade.

Antes da aula, o ambiente deve estar preparado. Entre em `http://127.0.0.1:8000/` com `aluno` / `Qualidade2026!`.

## 0–3 min — contexto e critérios

Abra **Cenários**, escolha um candidato e observe cenário, módulos alterados, defeitos críticos, limiar de cobertura (80%) e limiar de risco (0,80). Comece por `CAND-DEFEITOS` para observar problemas ou por `CAND-CORRIGIDO` para verificar evidências.

## 3–8 min — dados

Em **Dados**, localize uma duplicidade, um churn ausente e o vínculo `SIM-DEF-INEXISTENTE`. Leia a preparação proposta. Registre por que preservaria ou marcaria uma inconsistência e aplique a preparação. O bruto não será apagado.

## 8–12 min — indicadores e risco

No **Dashboard**, filtre um módulo. Diferencie:

- churn: linhas adicionadas + removidas;
- frequência: commits distintos;
- defeitos: contagem, não densidade;
- correção declarada: afirmação, não verificação.

Em **Predição**, priorize um módulo usando o escore real. Registre que o conjunto é sintético e que contribuição linear não prova causa.

## 12–20 min — dois casos propostos com IA

Em **Casos**, copie o pacote de contexto. Em uma IA de sua escolha, use por exemplo:

> Proponha exatamente dois casos conforme o JSON fornecido: um relacionado ao módulo de maior risco e outro de fronteira ou regressão. Não altere os requisitos. Explique fora do JSON quais hipóteses eu devo revisar.

Cole somente o JSON em **Importar**. Revise requisito, entradas e esperado de cada caso. Informe a ferramenta usada e suas verificações humanas no relatório. Então execute os dois casos. Não trate um caso aprovado como prova de que o esperado estava correto.

## 20–24 min — cobertura e visualização

Compare esperado e observado. Em **Cobertura**, distinga a seleção de dois casos da suíte obrigatória completa. Compare o teste fraco `T-FRACO-DESCONTO`, que só verifica aceitação, com `T-CUP-PERCENTUAL`, que verifica o desconto.

## 24–27 min — Gate e bot

Execute o Gate. `APROVADO` exige tudo; `BLOQUEADO` indica violação conhecida; `EVIDENCIAS_INSUFICIENTES` indica lacuna sem violação conhecida. Pergunte ao bot por que bloqueou e qual módulo investigar. Ele só resume dados reais.

## 27–30 min — relatório

Preencha contexto, tratamento, prioridade, casos, visualização, decisão, pendências, IA utilizada e checagens humanas. Marque o checklist sem pontuação e exporte Markdown ou HTML imprimível.

Nunca use dados pessoais reais. O pacote externo contém só contexto e amostra fictícios.

