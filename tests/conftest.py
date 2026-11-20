"""Общие фикстуры. Фабрики моделей лежат в tests/factories.py."""
import pytest


@pytest.fixture(autouse=True)
def _fixed_timezone(settings):
    """Тесты не должны зависеть от часового пояса машины."""
    settings.TIME_ZONE = "UTC"


@pytest.fixture
def superuser(db, django_user_model):
    return django_user_model.objects.create_superuser(
        username="admin", email="admin@example.com", password="pass12345"
    )
