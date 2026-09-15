#!/usr/bin/env python3
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise SystemExit(
            "Django nao esta instalado. Execute: python setup_lab.py prepare"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

