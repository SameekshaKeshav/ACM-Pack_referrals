"""Settings for load testing a local gunicorn. Never use these on Railway.

The same as pack_referrals.settings, plus:
- 500 errors are printed with their traceback, so a "database is locked" error
  can be told apart from other crashes. With DEBUG off, Django only emails them
  to ADMINS (unset), and Sentry is off locally, so otherwise they go nowhere.
- SQLITE_JOURNAL_MODE (e.g. "wal") sets the journal mode on every connection.
  Unset, SQLite uses its default rollback journal, as staging does.

Use with DJANGO_SETTINGS_MODULE=loadtests.loadtest_settings.
"""
import os

from pack_referrals.settings import *  # noqa: F401,F403
from pack_referrals.settings import DATABASES, LOGGING

LOGGING["loggers"]["django.request"] = {
    "handlers": ["console"],
    "level": "ERROR",
    "propagate": False,
}

JOURNAL_MODE = os.getenv("SQLITE_JOURNAL_MODE", "").strip()
if JOURNAL_MODE:
    DATABASES["default"]["OPTIONS"] = {"init_command": f"PRAGMA journal_mode={JOURNAL_MODE};"}
