# Loja Qualidade PUC

Laboratório executável da disciplina **Engenharia de Qualidade com IA e Análise de Dados**, ministrada pelo Dr. Rodrigo Fernandes dos Santos. A aplicação combina uma loja Django, defeitos didáticos reproduzíveis, dados sintéticos, regressão logística, execução segura de casos, cobertura real, Quality Gate determinístico, bot baseado em regras e relatório exportável.

Todo cliente, pedido, commit, defeito e histórico é **fictício**. A aplicação funciona localmente e não coleta CPF, cartão ou outros dados pessoais. A única interação externa opcional é a IA escolhida pelo aluno para propor dois casos; a revisão e a execução são locais.

## Requisitos e versões

- Python 3.12, 3.13 ou 3.14, em versão estável atual da série;
- Windows, macOS ou Linux;
- acesso à internet somente durante a primeira instalação de dependências;
- nenhuma API, GPU, Docker, Redis, Node.js ou banco externo.

Dependências são fixadas em `requirements.txt`: Django 5.2.17 LTS, pandas 3.0.5, scikit-learn 1.9.1, pytest 9.0.2, pytest-django 4.14.0 e coverage/pytest-cov. O SQLite vem com o Python. A combinação local registrada pela preparação aparece nos metadados do modelo.

## Preparação inicial

A preparação cria `.venv`, instala dependências, gera um segredo local em `.local/`, aplica migrações, cria dados brutos e tratados, treina o modelo, carrega a demonstração e mede evidências iniciais. É idempotente: uma nova execução não apaga pedidos, relatório ou testes do aluno, não retreina e não sobrescreve artefatos existentes.

### Windows

```bat
preparar.bat
iniciar.bat
```

Também funciona com `py -3 setup_lab.py prepare` e `py -3 setup_lab.py start`.

### macOS e Linux

```bash
./preparar.sh
./iniciar.sh
```

Se o ZIP não preservar permissão de execução, use `python3 setup_lab.py prepare` e depois `python3 setup_lab.py start`.

Abra <http://127.0.0.1:8000/>.

- usuário demonstrativo: `aluno`
- senha demonstrativa: `Qualidade2026!`

Essas credenciais são exclusivamente locais e didáticas. A senha é armazenada pelo mecanismo nativo de hash do Django.

## Uso cotidiano e restauração

`python setup_lab.py start` apenas verifica e inicia o servidor no loopback; não apaga dados, reinstala ou retreina. Para outra porta, use `--port 8010`.

A restauração é deliberadamente separada e exige confirmação:

```bash
python setup_lab.py reset --confirm
```

Ela também está em **Laboratório → Restaurar**. A ação remove o progresso da conta demonstrativa e recria a base didática; não altera o Git nem o histórico bruto reproduzível.

## Diagnóstico

```bash
python setup_lab.py doctor
```

O comando identifica Python incompatível, dependência ausente, porta ocupada, falha de configuração/migração e modelo ausente. Correções usuais:

- `Python 3.12 ou superior é necessário`: instale uma versão suportada e rode a preparação com ela;
- `dependência ausente`: rode `python setup_lab.py prepare` novamente;
- `porta 8000 ocupada`: use `python setup_lab.py start --port 8010`;
- falha de migração: confirme permissão de escrita na pasta e execute `.venv/bin/python manage.py migrate` (Windows: `.venv\Scripts\python`);
- modelo ausente/corrompido: execute o comando `train_risk_model --force`; até lá o Gate retorna evidência insuficiente.

## Regras comerciais

Dinheiro é persistido em centavos inteiros; nunca se usa `float` para preço. O subtotal soma `preço unitário × quantidade`. Cupom percentual usa divisão inteira em centavos, truncando frações abaixo de um centavo; aplica-se depois do subtotal, respeita mínimo e teto, e nunca torna o total negativo. O instante deve estar no intervalo inclusivo `valid_from ≤ agora ≤ valid_until`, no fuso `America/Sao_Paulo`.

Pagamento mock recusado cria registro recusado para auditoria, mas não consome estoque. Pagamento aprovado valida e debita estoque dentro de uma transação curta. No SQLite, a consistência não depende de `select_for_update`: a referência corrigida executa `UPDATE` condicional com `stock__gte` e reserva uma chave de idempotência única. O mesmo usuário e a mesma chave retornam o primeiro pedido e não repetem o débito.

Requisitos identificados, defeitos e oráculos estão em [Guia do professor](docs/GUIA_PROFESSOR.md). O comportamento defeituoso vive somente em políticas explícitas de cenário; autenticação e executor não recebem falhas intencionais.

## Validação de desenvolvimento

```bash
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=loja --cov=laboratorio --cov-report=term-missing --cov-report=html
.venv/bin/python manage.py check
```

No Windows, troque `.venv/bin/python` por `.venv\Scripts\python`. A suíte de engenharia pode passar justamente porque reproduz corretamente um defeito intencional; isso não significa que o Gate didático do candidato defeituoso esteja aprovado.

## Documentação

- [Guia do aluno — percurso de 30 minutos](docs/GUIA_ALUNO.md)
- [Guia do professor — requisitos e cinco defeitos](docs/GUIA_PROFESSOR.md)
- [Arquitetura e decisões](docs/ARQUITETURA.md)
- [Catálogo, limpeza e métricas dos dados](docs/DADOS.md)
- [Modelo preditivo e avaliação temporal](docs/MODELO.md)
- [Schema e executor de testes](docs/TESTES_E_EXECUTOR.md)
- [Quality Gate e bot](docs/GATE_E_BOT.md)
- [Desenvolvimento, testes e CI](docs/DESENVOLVIMENTO.md)
- [Referências oficiais consultadas](docs/REFERENCIAS.md)

## Estrutura resumida

```text
config/            configuração Django e URLs
loja/              modelos, regras e serviços comerciais
laboratorio/       dados, ML, cenários, executor, Gate, bot e relatório
templates/ static/ interface responsiva sem CDN
data/ artifacts/   saídas locais reproduzíveis, ignoradas pelo Git
schemas/           contrato JSON versionado
tests/             suíte de engenharia e regras do laboratório
docs/              material do aluno, professor e referência técnica
```

Este projeto é um laboratório educacional. A release é simulada e não publica a aplicação.
