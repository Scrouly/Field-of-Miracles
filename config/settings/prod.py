"""Боевые настройки для мультиборда.

Сервер работает по обычному http в локальной сети, поэтому SECURE_SSL_REDIRECT и
HSTS намеренно не включены: без сертификата они сломали бы доступ к экрану.
"""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import SECRET_KEY as _SECRET_KEY

DEBUG = False

secret_key = os.environ.get("DJANGO_SECRET_KEY") or _SECRET_KEY or load_secret_key()
if not secret_key:
    raise ImproperlyConfigured(
        "Не задан SECRET_KEY: положите ключ в файл secret.key в корне проекта "
        "или задайте переменную окружения DJANGO_SECRET_KEY."
    )
SECRET_KEY = secret_key

SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Разрешаем подключение с любых адресов локальной сети для пульта ведущего
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")
    if host.strip()
]

STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"
