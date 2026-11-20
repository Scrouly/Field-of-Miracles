"""Боевые настройки для мультиборда.

Сервер работает по обычному http в локальной сети, поэтому SECURE_SSL_REDIRECT и
HSTS намеренно не включены: без сертификата они сломали бы доступ к экрану.
"""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import SECRET_KEY as _SECRET_KEY

DEBUG = False

if not _SECRET_KEY:
    raise ImproperlyConfigured(
        "Не задан SECRET_KEY: положите ключ в файл secret.key в корне проекта "
        "или задайте переменную окружения DJANGO_SECRET_KEY."
    )
SECRET_KEY = _SECRET_KEY

SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
