import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or secrets.token_urlsafe(48)
DEBUG = os.environ.get("LITCHAT_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "chat.middleware.LoopbackOnlyMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "litchat.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
            ],
        },
    },
]

WSGI_APPLICATION = "litchat.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LITCHAT_MODELS = {
    "openai": os.environ.get("LITCHAT_OPENAI_MODEL", "gpt-5.6-luna"),
    "anthropic": os.environ.get(
        "LITCHAT_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"
    ),
    "google": os.environ.get("LITCHAT_GOOGLE_MODEL", "gemini-3.8-flash"),
}

LITCHAT_PROXY_TIMEOUT = float(os.environ.get("LITCHAT_PROXY_TIMEOUT", "90"))
