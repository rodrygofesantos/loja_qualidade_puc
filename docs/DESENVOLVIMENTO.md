# Desenvolvimento, testes e CI

## Comandos

```bash
python setup_lab.py prepare
.venv/bin/python manage.py check
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=loja --cov=laboratorio --cov-report=json --cov-report=html
```

Geradores são reproduzíveis:

```bash
.venv/bin/python manage.py generate_lab_data --force
.venv/bin/python manage.py train_risk_model --force
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py measure_demo_evidence
```

`seed_demo` é idempotente e preserva progresso. `measure_demo_evidence` preserva uma medição completa existente por candidato. Somente `reset_lab --confirm` remove progresso.

## Dois níveis

Testes do laboratório são casos armazenados cujo `outcome` demonstra regras da loja em um cenário. Suíte de engenharia (`pytest`) verifica domínio, persistência, defeitos, gerador, ML, schema, executor, Gate, bot, interface e exportação. A CI pode passar por ter observado corretamente falhas no cenário defeituoso; o Gate didático continuará bloqueado.

Cobertura de engenharia inclui aplicações; cobertura didática tem escopo menor e estável. Não compare ou some percentuais sem escopo, revisão e denominador iguais.

## CI

GitHub Actions instala do zero, migra, gera dados/modelo, semeia, executa checks e pytest em Windows, macOS e Linux com Python 3.12; Ubuntu também cobre 3.14. Resultado local não é alegado como execução nos demais sistemas. O status efetivo deve ser lido nos jobs do commit do PR.

Artefatos locais, SQLite, segredo, `.venv`, caches e relatórios temporários são ignorados. Migrações, gerador, schema, documentação e configuração de testes são versionados.

