"""Prepare a throwaway local database for the write load test.

Migrates the database at SQLITE_PATH, creates a reader and a writer account
with a conversation between them, and prints the environment variables
locustfile.py needs. Safe to run again: it reuses the accounts and conversation.

Run from the repository root (see docs/load-test-report.md):

    SQLITE_PATH=/tmp/lt.sqlite3 python -m loadtests.setup_local
"""
import os
import sys

import django

if not os.getenv("SQLITE_PATH"):
    sys.exit("Set SQLITE_PATH to a throwaway database file, not your dev or staging database.")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "loadtests.loadtest_settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402
from rest_framework_simplejwt.tokens import AccessToken  # noqa: E402

from chat.models import Conversation, ConversationParticipant  # noqa: E402

call_command("migrate", verbosity=0)

User = get_user_model()
reader, _ = User.objects.get_or_create(username="loadtest_reader")
writer, _ = User.objects.get_or_create(username="loadtest_writer")

conversation = (
    Conversation.objects.filter(conversation_participants__user=reader)
    .filter(conversation_participants__user=writer)
    .first()
)
if conversation is None:
    conversation = Conversation.objects.create()
    ConversationParticipant.objects.create(conversation=conversation, user=reader)
    ConversationParticipant.objects.create(conversation=conversation, user=writer)

print(f"export LOADTEST_TOKEN={AccessToken.for_user(reader)}")
print(f"export LOADTEST_SENDER_TOKEN={AccessToken.for_user(writer)}")
print(f"export LOADTEST_CONVERSATION_ID={conversation.pk}")
