import importlib
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured


def test_index_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200


def test_index_page_has_no_external_resources(client):
    """Работа офлайн: на странице нет ссылок на CDN и внешние шрифты."""
    html = client.get("/").content.decode()
    assert "http://" not in html
    assert "https://" not in html


def test_production_settings_require_secret_key(monkeypatch, tmp_path):
    """В prod без своего SECRET_KEY сервер не должен стартовать."""
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    monkeypatch.setenv("DJANGO_SECRET_KEY_FILE", str(tmp_path / "нет-такого-файла.key"))
    for name in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(name, None)
    with pytest.raises(ImproperlyConfigured):
        importlib.import_module("config.settings.prod")


def test_production_settings_read_secret_key_from_file(monkeypatch, tmp_path):
    key_file = tmp_path / "secret.key"
    key_file.write_text("  ключ-из-файла-для-теста  \n", encoding="utf-8")
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    monkeypatch.setenv("DJANGO_SECRET_KEY_FILE", str(key_file))
    for name in ("config.settings.prod", "config.settings.base"):
        sys.modules.pop(name, None)
    prod = importlib.import_module("config.settings.prod")
    assert prod.SECRET_KEY == "ключ-из-файла-для-теста"
    assert prod.DEBUG is False
