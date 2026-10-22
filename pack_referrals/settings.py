"""
Django settings for pack_referrals project.
"""

import os
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

EMAIL_HOST = os.getenv("EMAIL_HOST", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT") or 587)  # empty value falls back to 587
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", default=True)

if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

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

# EMAIL_BACKEND is set above from EMAIL_HOST: SMTP when configured, console
# otherwise, so verification codes print to the runserver output in development.
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@packreferrals.ncsu.edu")

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
    )

# OpenAPI schema and Swagger UI (served at /api/schema/ and /api/docs/).
SPECTACULAR_SETTINGS = {
    "TITLE": "Pack Referrals API",
    "DESCRIPTION": "Verified NC State referral network. Send `Authorization: Bearer <token>`.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
