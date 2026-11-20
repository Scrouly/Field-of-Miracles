from .base import *  # noqa: F401,F403
from .base import SECRET_KEY as _SECRET_KEY

DEBUG = False
SECRET_KEY = _SECRET_KEY or "test-only-insecure-key"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
