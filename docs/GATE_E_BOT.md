# Quality Gate e quality bot

## Critérios iniciais

| Regra | Aprovação |
|---|---|
| Defeitos críticos | lista aberta vazia |
| Testes obrigatórios | lista não vazia; todos presentes na revisão atual e aprovados |
| Cobertura | denominador real > 0 e percentual ≥ 80% |
| Correções declaradas | mesmo caso/revisão/requisito falha no defeito e passa corrigido |
| Risco | todo módulo alterado tem score válido estritamente < 0,80 |
| Integridade | candidato, cenário, código, casos, execução, modelo e configuração compatíveis |

Uma lista vazia ou denominador ausente não vale 100%; score ausente não vira zero. Sem correção declarada, a regra é não aplicável. Sem módulo alterado, o candidato não é aprovado como atalho.

Violação conhecida produz `BLOQUEADO`, mesmo com lacunas adicionais. Sem violação, qualquer falta/erro produz `EVIDENCIAS_INSUFICIENTES`. Só o restante produz `APROVADO`.

Alterar limiares cria `GateConfig` nova e não reescreve avaliações. Alterar casos, cenário, código ou modelo deixa o snapshot anterior incompatível. O endpoint de liberação verifica a avaliação exibida, reexecuta o Gate e registra somente `ReleaseSimulation`; não publica nada.

## Bot

O bot oferece seis perguntas fechadas. Lê a última avaliação e execução e inclui IDs/valores. “Qual módulo?” escolhe o maior score e avisa que isso é prioridade estatística, não causa. Se dado não existe, indica a evidência ausente. Ele não executa pagamento/teste, confirma correção, muda Gate ou libera candidato.

