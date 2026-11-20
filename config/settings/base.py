"""Общие настройки. Всё, что отличается между dev/prod/test, лежит в одноимённых файлах."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def load_secret_key() -> str | None:
    """SECRET_KEY из переменной окружения или из файла secret.key (в git не попадает).

    Возвращает None, если ключ нигде не задан: dev и test подставят временный,
    prod откажется стартовать.
    """
    key = os.environ.get("DJANGO_SECRET_KEY")
    if key:
        return key
    key_file = Path(os.environ.get("DJANGO_SECRET_KEY_FILE", BASE_DIR / "secret.key"))
    if key_file.is_file():
        key = key_file.read_text(encoding="utf-8").strip()
        return key or None
    return None


SECRET_KEY = load_secret_key()
DEBUG = False

# Для работы по локальной сети (пульт ведущего на втором устройстве)
# адреса задаются через DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,192.168.1.50".
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Локальные приложения
    "apps.core",
    "apps.game",
    "apps.studio",
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
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Minsk"
USE_I18N = True
USE_TZ = True

# Всё лежит в проекте: никаких CDN (работа полностью офлайн).
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
