import os
import secrets
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_DIR = BASE_DIR / ".local"


def _local_secret():
    override = os.environ.get("DJANGO_SECRET_KEY")
    if override:
        return override
    LOCAL_DIR.mkdir(exist_ok=True)
    secret_file = LOCAL_DIR / "secret_key.txt"
    if not secret_file.exists():
        secret_file.write_text(secrets.token_urlsafe(64), encoding="utf-8")
    return secret_file.read_text(encoding="utf-8").strip()


SECRET_KEY = _local_secret()
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "loja",
    "laboratorio",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "laboratorio.context_processors.lab_context",
            ],
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

DB_PATH = Path(os.environ.get("LAB_DB_PATH", BASE_DIR / "db.sqlite3"))
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_PATH,
        "OPTIONS": {"timeout": 10, "transaction_mode": "IMMEDIATE"},
    }
}

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "laboratorio:overview"
LOGOUT_REDIRECT_URL = "login"

LAB_REVISION = os.environ.get("LAB_REVISION", "lab-v1")
LAB_MODEL_PATH = Path(os.environ.get("LAB_MODEL_PATH", BASE_DIR / "artifacts/model/risk_pipeline.joblib"))
LAB_MODEL_METADATA_PATH = Path(os.environ.get("LAB_MODEL_METADATA_PATH", BASE_DIR / "artifacts/model/metadata.json"))
LAB_EXECUTION_DIR = Path(os.environ.get("LAB_EXECUTION_DIR", BASE_DIR / "artifacts/executions"))

