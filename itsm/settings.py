"""Settings. Every secret and host-specific value comes from environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(env(name, str(default))).lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [v.strip() for v in env(name, default).split(",") if v.strip()]


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me" if DEBUG else "")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "accounts",
    "tickets",
    "integrations",
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

ROOT_URLCONF = "itsm.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "itsm.wsgi.application"

if env("POSTGRES_HOST"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "itsm"),
        "USER": env("POSTGRES_USER", "itsm"),
        "PASSWORD": env("POSTGRES_PASSWORD", ""),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", BASE_DIR / "media"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# Session security
SESSION_COOKIE_AGE = int(env("SESSION_COOKIE_AGE", str(60 * 60 * 8)))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
MAX_UPLOAD_SIZE = int(env("MAX_UPLOAD_SIZE", str(10 * 1024 * 1024)))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE

# SMTP (used for invitations, password resets and notifications)
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("SMTP_HOST", "localhost")
EMAIL_PORT = int(env("SMTP_PORT", "587"))
EMAIL_HOST_USER = env("SMTP_USERNAME", "")
EMAIL_HOST_PASSWORD = env("SMTP_PASSWORD", "")
EMAIL_USE_TLS = env_bool("SMTP_USE_TLS", True)
EMAIL_USE_SSL = env_bool("SMTP_USE_SSL", False)
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = env("SMTP_FROM", "IT Service Desk <servicedesk@example.com>")
PASSWORD_RESET_TIMEOUT = 60 * 60 * 2

# Microsoft Graph. Secrets come only from the environment, never from the database.
# M365_MODE=dry_run (default) logs and reports planned actions without changing the tenant.
# M365_MODE=live performs real Graph calls and requires all four credentials.
MICROSOFT365 = {
    "TENANT_ID": env("M365_TENANT_ID", ""),
    "CLIENT_ID": env("M365_CLIENT_ID", ""),
    "CLIENT_SECRET": env("M365_CLIENT_SECRET", ""),
    "DEFAULT_LICENSE_SKU_ID": env("M365_DEFAULT_LICENSE_SKU_ID", ""),
    "MODE": env("M365_MODE", "dry_run"),
    "DEFAULT_UPN_DOMAIN": env("M365_UPN_DOMAIN", ""),
}

PORTAL_BASE_URL = env("PORTAL_BASE_URL", "http://localhost:8000")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.TokenAuthentication",
                                       "rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

# n8n: the service account that inbound workflow actions are performed as.
N8N_ACTOR_USERNAME = env("N8N_ACTOR_USERNAME", "n8n-service")
N8N_INBOUND_SECRET_ENV = "N8N_INBOUND_SECRET"
CORS_NOTE = "Next.js and mobile clients use token auth against /api/v1 (Next proxies same-origin)."
