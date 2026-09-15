# Referências oficiais consultadas

Consulta técnica realizada em 14–15/09/2026 para as versões adotadas:

- [Django 5.2 — bancos de dados e notas de SQLite](https://docs.djangoproject.com/en/5.2/ref/databases/): transações curtas, modo `IMMEDIATE` e ausência de efeito de `select_for_update()` no SQLite;
- [Django 5.2 — transações](https://docs.djangoproject.com/en/5.2/topics/db/transactions/): blocos `atomic()` e rollback por exceção;
- [Django 5.2 — notas da versão LTS](https://docs.djangoproject.com/en/5.2/releases/5.2/): compatibilidade de Python;
- [coverage.py — JSON](https://coverage.readthedocs.io/en/latest/commands/cmd_json.html): geração de resultados estruturados reais;
- [scikit-learn — pitfalls](https://scikit-learn.org/stable/common_pitfalls.html): pipeline e prevenção de vazamento;
- [scikit-learn — TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html): referência temporal. O laboratório usa cortes próprios por versão para manter todos os módulos da mesma versão juntos.

Versões exatas de pacotes foram confirmadas no índice oficial do Python durante a implementação e estão integralmente fixadas em `requirements.txt`.

