import os
import tempfile
import uuid
from pathlib import Path

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
os.environ.setdefault("APP_DATA_DIR", str(Path(__file__).resolve().parent.parent / ".test-data"))

from .settings import *  # noqa: F403

DATABASES["default"]["NAME"] = DATA_DIR / "tests.sqlite3"  # noqa: F405
DATABASES["default"]["TEST"] = {  # noqa: F405
    "NAME": (
        Path(tempfile.gettempdir())
        / f"grounded-growth-pytest-{os.getpid()}-{uuid.uuid4().hex}.sqlite3"
    )
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}
STATIC_ROOT = DATA_DIR / "staticfiles"  # noqa: F405
STATIC_ROOT.mkdir(parents=True, exist_ok=True)
WHITENOISE_USE_FINDERS = True
