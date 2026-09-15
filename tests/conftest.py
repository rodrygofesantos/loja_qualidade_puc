import pytest
from django.core.management import call_command

from laboratorio.ml import artifact_paths, train_model


@pytest.fixture(scope="session", autouse=True)
def model_artifact_available(django_db_setup, django_db_blocker):
    model_path, metadata_path = artifact_paths()
    if not model_path.exists() or not metadata_path.exists():
        train_model(force=True)


@pytest.fixture
def demo_user(db):
    call_command("seed_demo", verbosity=0)
    from django.contrib.auth import get_user_model

    return get_user_model().objects.get(username="aluno")

