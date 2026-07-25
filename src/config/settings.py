from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    return value if value != "" else default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def split_env(name: str, default: str = "") -> list[str]:
    raw_value = env(name, default) or ""
    return [item.strip() for item in raw_value.split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = split_env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = split_env("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8000")
TIME_ZONE = env("DJANGO_TIME_ZONE", "UTC")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django_htmx",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "apps.accounts",
    "apps.communities",
    "apps.content",
    "apps.core",
    "apps.moderation",
    "apps.notifications",
    "apps.progress",
    "apps.workouts",
]

if DEBUG:
    INSTALLED_APPS.append("django_browser_reload")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

if DEBUG:
    MIDDLEWARE.insert(-2, "django_browser_reload.middleware.BrowserReloadMiddleware")

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "src" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.notifications.context_processors.notifications_context",
            ],
        },
    }
]

def build_database_config() -> dict[str, object]:
    if env_bool("USE_SQLITE", False):
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }

    engine = env("DATABASE_ENGINE", "django.db.backends.postgresql")
    if engine == "django.db.backends.sqlite3":
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("DATABASE_NAME", str(BASE_DIR / "db.sqlite3")),
        }

    return {
        "ENGINE": engine,
        "NAME": env("DATABASE_NAME", "spotter"),
        "USER": env("DATABASE_USER", "spotter"),
        "PASSWORD": env("DATABASE_PASSWORD", "spotter"),
        "HOST": env("DATABASE_HOST", "localhost"),
        "PORT": env("DATABASE_PORT", "5432"),
    }


DATABASES = {"default": build_database_config()}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1
LOGIN_REDIRECT_URL = "/"
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGOUT_ON_GET = True

LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "assets", BASE_DIR / "src" / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "noreply@example.com")

INTERNAL_IPS = ["127.0.0.1", "::1"]
