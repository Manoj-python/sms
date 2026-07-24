"""Django settings for the SMSquare Customer Portal.

Business/AllCloud config (tokens, helpline number, OTP policy, ...) lives in
portal/config.py (pydantic-settings, reading the same .env this file does
for DATABASE_URL/SECRET_KEY) — see that module for why it's kept separate.
"""

from pathlib import Path

from portal.config import get_settings
from portal.db_url import parse_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
_settings = get_settings()

SECRET_KEY = _settings.secret_key
DEBUG = not _settings.is_prod
# Local demo/testing regardless of APP_ENV (this app is only ever run
# locally right now, no real deployment host yet) — always allow localhost;
# widen with a real domain via ALLOWED_HOSTS once actually deployed.
ALLOWED_HOSTS = ["*"] if DEBUG else ["localhost", "127.0.0.1"]

# No django.contrib.auth/sessions/admin — the portal rolls its own signed-
# cookie + DB-backed session (portal.services.session_service), matching the
# FastAPI version exactly (itsdangerous + Fernet-encrypted mobile column).
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "portal",
]

MIDDLEWARE = [
    # Deliberately just the one middleware — the FastAPI portal only ever had
    # a single @app.middleware("http") hook (security_headers) too. Mixing in
    # a sync built-in like CommonMiddleware alongside our async-only
    # SecurityHeadersMiddleware trips up Django's sync/async adaptation.
    "portal.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"

# Jinja2 as the (sole) template backend — lets the FastAPI portal's existing
# Jinja templates (dmy filter, `{{ t('key') }}`, Jinja `format` filter, `is
# defined` tests) carry over unchanged instead of being rewritten into DTL.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [BASE_DIR / "portal" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "environment": "portal.jinja2_env.environment",
            "context_processors": [
                "portal.context_processors.portal_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": parse_database_url(_settings.database_url, BASE_DIR)}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "portal" / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # httpx logs the full request URL at INFO level, including query
        # strings — for GET calls (OTP delivery, AllCloud lookups) that
        # leaks OTPs/mobile numbers into the server log verbatim, bypassing
        # our own redaction in otp_service/allcloud_auth.
        "httpx": {"level": "WARNING"},
        "django.server": {"level": "INFO", "handlers": ["console"], "propagate": False},
    },
}
