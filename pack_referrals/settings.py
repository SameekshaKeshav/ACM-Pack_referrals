"""
Django settings for pack_referrals project.
"""

import os
import warnings
from datetime import timedelta
from pathlib import Path

import sentry_sdk
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set. Copy .env.example to .env and set SECRET_KEY."
    )

DEBUG = _env_bool("DEBUG", default=False)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")

# Email. Unset EMAIL_BACKEND prints mail to the console, for local development.
# Staging sets it to Anymail's Brevo backend, which sends over Brevo's HTTPS
# API, because Railway's plan blocks outbound SMTP.
EMAIL_BACKEND = (
    os.getenv("EMAIL_BACKEND", "").strip()
    or "django.core.mail.backends.console.EmailBackend"
)

ANYMAIL = {
    "BREVO_API_KEY": os.getenv("BREVO_API_KEY", "").strip(),
    # (connect, read) seconds. Anymail's default is 30, the same as gunicorn's
    # worker timeout, so a hung provider could get the worker killed mid-request.
    "REQUESTS_TIMEOUT": (3.05, 10),
}

# Anymail only reads the key when the first email is sent, so without this a
# missing key would surface as a failed signup rather than a failed deploy.
if (
    EMAIL_BACKEND == "anymail.backends.brevo.EmailBackend"
    and not ANYMAIL["BREVO_API_KEY"]
):
    raise RuntimeError(
        "EMAIL_BACKEND is the Brevo backend but BREVO_API_KEY is not set."
    )

# A warning, not an error: running with DEBUG off locally (e.g. to test error
# pages) is legitimate. On staging it means codes only reach the logs.
if not DEBUG and EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
    warnings.warn(
        "DEBUG is off but EMAIL_BACKEND is the console backend, so verification "
        "codes are printed to the logs instead of emailed. Set EMAIL_BACKEND."
    )

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

COMMIT_HASH = os.getenv("RAILWAY_GIT_COMMIT_SHA")

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "anymail",
    "api",
    "accounts",
    "companies",
    "connections",
    "chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Below WhiteNoise so static file requests are served before reaching it
    # and don't flood the request log.
    "pack_referrals.middleware.RequestLoggingMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pack_referrals.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "pack_referrals.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("SQLITE_PATH") or BASE_DIR / "db.sqlite3",
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

# Built React app (npm run build in frontend/). collectstatic copies it into
# STATIC_ROOT, so WhiteNoise serves it under STATIC_URL.
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
STATICFILES_DIRS = [FRONTEND_DIST] if FRONTEND_DIST.exists() else []

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    # JWT is how API clients authenticate. SessionAuthentication stays so the
    # Django admin and the DRF browsable API keep working in development.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Closed by default. Endpoints that must stay public set AllowAny
    # explicitly: auth signup/verify and the health checks.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Applied per view via throttle classes in accounts.throttling.
    "DEFAULT_THROTTLE_RATES": {
        # Requesting a code emails a stranger and runs a slow hash, so it is
        # both an abuse vector and a cheap way to burn server CPU.
        "code_request": os.getenv("THROTTLE_CODE_REQUEST", "5/15min"),
        # Submitting a code. The per-code attempt cap is the real defence
        # against guessing; this bounds flooding from one source.
        "verify_attempt": os.getenv("THROTTLE_VERIFY_ATTEMPT", "10/15min"),
        # Sending a chat message, per signed-in user (chat.throttling).
        "message_send": os.getenv("THROTTLE_MESSAGE_SEND", "30/min"),
    },
    # How many proxies sit in front of the app. Throttles use it to find the
    # client's IP in X-Forwarded-For. Unset, DRF keys on the whole header,
    # which the client controls, so a new value each request skips the limit.
    "NUM_PROXIES": int(os.getenv("NUM_PROXIES")) if os.getenv("NUM_PROXIES") else None,
}

# A code is destroyed after this many wrong guesses, so a six-digit code
# cannot be brute-forced regardless of how many addresses an attacker has.
VERIFICATION_MAX_ATTEMPTS = int(os.getenv("VERIFICATION_MAX_ATTEMPTS") or 5)

# --- Authentication (BE1) -------------------------------------------------
# Signup is restricted to this domain; see accounts/validators.py.
ALLOWED_SIGNUP_EMAIL_DOMAIN = (
    os.getenv("ALLOWED_SIGNUP_EMAIL_DOMAIN", "ncsu.edu").strip().lstrip("@")
)

# Lifetime of an emailed verification code, in minutes.
VERIFICATION_CODE_TTL_MINUTES = int(os.getenv("VERIFICATION_CODE_TTL_MINUTES") or 10)

ACCESS_TOKEN_LIFETIME_HOURS = int(os.getenv("ACCESS_TOKEN_LIFETIME_HOURS") or 24)
REFRESH_TOKEN_LIFETIME_DAYS = int(os.getenv("REFRESH_TOKEN_LIFETIME_DAYS") or 7)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=ACCESS_TOKEN_LIFETIME_HOURS),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS),
}

# The address must be a sender verified in Brevo, or Brevo rejects the send.
# It's the Gmail account that owns the Brevo account; the name is what inboxes
# show as the sender.
DEFAULT_FROM_EMAIL = (
    os.getenv("DEFAULT_FROM_EMAIL", "").strip()
    or "Pack Referrals <packreferrals.acm@gmail.com>"
)

# --- Logging --------------------------------------------------------------
# Level for the request log (pack_referrals.middleware). WARNING hides the
# per-request INFO lines, e.g. in CI.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "class": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "pack_referrals.middleware": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        # Failed verification-code sends (accounts.views) are logged as errors.
        "accounts": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# --- Error tracking (Sentry) ----------------------------------------------
# Only enabled when SENTRY_DSN is set, so CI and local runs without it don't
# report to Sentry (some tests raise exceptions on purpose).
SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        release=COMMIT_HASH,
        # Variable values and request bodies hold emails, verification codes
        # and chat messages, and Sentry sends both by default even with
        # send_default_pii off. Its scrubber only matches key names, so it
        # misses an email inside another value's repr. The stack trace (files,
        # functions, lines) and request URL are still sent.
        include_local_variables=False,
        max_request_body_size="never",
    )

# OpenAPI schema and Swagger UI (served at /api/schema/ and /api/docs/).
SPECTACULAR_SETTINGS = {
    "TITLE": "Pack Referrals API",
    "DESCRIPTION": "Verified NC State referral network. Send `Authorization: Bearer <token>`.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
