#!/usr/bin/env python3
import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
MIN_PYTHON = (3, 12)


def fail(message):
    raise SystemExit(f"ERRO: {message}")


def check_python():
    if sys.version_info < MIN_PYTHON:
        fail(f"Python 3.12 ou superior e necessario; encontrado {sys.version.split()[0]}. Instale uma versao compativel e tente novamente.")


def venv_python():
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(command, *, timeout=None, check=True):
    try:
        return subprocess.run([str(piece) for piece in command], cwd=ROOT, shell=False, check=check, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        fail(f"Tempo limite excedido ao executar {' '.join(map(str, command))}.")
    except subprocess.CalledProcessError as exc:
        fail(f"Comando falhou (codigo {exc.returncode}): {' '.join(map(str, command))}")


def ensure_venv():
    if not venv_python().exists():
        print("Criando ambiente virtual local em .venv ...")
        run([sys.executable, "-m", "venv", VENV])
    return venv_python()


def prepare():
    check_python()
    python = ensure_venv()
    print("Instalando dependencias fixadas ...")
    run([python, "-m", "pip", "install", "--disable-pip-version-check", "-r", ROOT / "requirements.txt"])
    steps = [
        ([python, "manage.py", "migrate", "--noinput"], "aplicar migracoes"),
        ([python, "manage.py", "generate_lab_data"], "preparar dados"),
        ([python, "manage.py", "train_risk_model"], "preparar modelo"),
        ([python, "manage.py", "seed_demo"], "criar dados demonstrativos"),
        ([python, "manage.py", "measure_demo_evidence"], "medir evidencias iniciais"),
        ([python, "manage.py", "check"], "verificar configuracao"),
    ]
    started = time.monotonic()
    for command, label in steps:
        print(f"Etapa: {label} ...")
        run(command, timeout=180)
    print(f"\nPreparacao concluida em {time.monotonic() - started:.1f}s.")
    print("Endereco: http://127.0.0.1:8000/")
    print("Usuario demonstrativo: aluno")
    print("Senha demonstrativa: Qualidade2026!")
    print("Inicie com: python setup_lab.py start")


def doctor(port):
    check_python()
    if not 1 <= port <= 65535:
        fail("A porta deve estar entre 1 e 65535.")
    problems = []
    if not venv_python().exists():
        problems.append("Ambiente .venv ausente: execute prepare.")
    else:
        result = subprocess.run([str(venv_python()), "-c", "import django,pandas,sklearn,pytest,coverage"], cwd=ROOT, capture_output=True, text=True, shell=False)
        if result.returncode:
            problems.append("Dependencia ausente ou incompativel: execute prepare novamente.")
        check = subprocess.run([str(venv_python()), "manage.py", "check"], cwd=ROOT, capture_output=True, text=True, shell=False)
        if check.returncode:
            problems.append(f"Falha na configuracao/migracao: {check.stderr.strip()}")
        migrations = subprocess.run([str(venv_python()), "manage.py", "migrate", "--check"], cwd=ROOT, capture_output=True, text=True, shell=False)
        if migrations.returncode:
            problems.append("Existem migracoes pendentes: execute prepare novamente.")
        model = ROOT / "artifacts/model/risk_pipeline.joblib"
        if not model.exists():
            problems.append("Modelo ausente: execute prepare ou manage.py train_risk_model.")
        else:
            model_check = subprocess.run([str(venv_python()), "manage.py", "shell", "-c", "from laboratorio.ml import load_artifact; load_artifact()"], cwd=ROOT, capture_output=True, text=True, shell=False)
            if model_check.returncode:
                problems.append("Modelo corrompido ou incompativel: execute manage.py train_risk_model --force.")
    with socket.socket() as probe:
        probe.settimeout(0.2)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            problems.append(f"Porta {port} ocupada. Use: python setup_lab.py start --port OUTRA_PORTA")
    if problems:
        print("Diagnostico encontrou:")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)
    print("Diagnostico concluido: Python, dependencias, configuracao, modelo e porta disponiveis.")


def start(port):
    if not venv_python().exists():
        fail("Ambiente nao preparado. Execute: python setup_lab.py prepare")
    doctor(port)
    print(f"Abrindo apenas no computador local: http://127.0.0.1:{port}/")
    run([venv_python(), "manage.py", "runserver", f"127.0.0.1:{port}"])


def reset(confirm):
    if not confirm:
        fail("Restauracao apaga o progresso local. Repita com: python setup_lab.py reset --confirm")
    if not venv_python().exists():
        fail("Ambiente nao preparado.")
    run([venv_python(), "manage.py", "reset_lab", "--confirm"])


def main():
    parser = argparse.ArgumentParser(description="Inicializador multiplataforma do Laboratorio Loja Qualidade PUC")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare", help="cria ambiente, instala e prepara dados uma vez")
    start_parser = commands.add_parser("start", help="inicia sem apagar dados nem retreinar")
    start_parser.add_argument("--port", type=int, default=8000)
    doctor_parser = commands.add_parser("doctor", help="diagnostica Python, dependencias, porta, migracoes e modelo")
    doctor_parser.add_argument("--port", type=int, default=8000)
    reset_parser = commands.add_parser("reset", help="restaura explicitamente o progresso local")
    reset_parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "start":
        start(args.port)
    elif args.command == "doctor":
        doctor(args.port)
    else:
        reset(args.confirm)


if __name__ == "__main__":
    main()
