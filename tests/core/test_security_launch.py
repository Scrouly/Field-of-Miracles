"""Tests for Launch scripts and Security settings (Task 18)."""

from pathlib import Path
import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import Client


def test_launch_files_exist():
    base_dir = settings.BASE_DIR
    assert (base_dir / "start.bat").is_file()
    assert (base_dir / "scripts" / "kiosk.ps1").is_file()
    assert (base_dir / "config" / "settings" / "prod.py").is_file()


def test_prod_settings_security(monkeypatch):
    import importlib
    monkeypatch.setenv("DJANGO_SECRET_KEY", "test-secret-key-for-production-12345")

    import config.settings.prod as prod
    importlib.reload(prod)

    assert prod.DEBUG is False
    assert prod.SESSION_COOKIE_HTTPONLY is True
    assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod.X_FRAME_OPTIONS == "DENY"


def test_prod_settings_raises_without_secret_key(monkeypatch):
    import importlib
    from config.settings import base

    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    monkeypatch.setattr(base, "SECRET_KEY", None)
    monkeypatch.setattr(base, "load_secret_key", lambda: None)

    with pytest.raises(ImproperlyConfigured) as exc:
        import config.settings.prod as prod
        importlib.reload(prod)
    assert "Не задан SECRET_KEY" in str(exc.value)


def test_pin_protection_on_host_and_studio():
    client = Client()

    # Host view requires PIN
    resp_host = client.get("/host/")
    assert resp_host.status_code == 200
    assert "Пульт ведущего" in resp_host.content.decode("utf-8")
    assert "pin-input" in resp_host.content.decode("utf-8")

    # Studio view redirects to login when unauthorized
    resp_studio = client.get("/studio/")
    assert resp_studio.status_code == 302
    assert "/studio/login/" in resp_studio.url
