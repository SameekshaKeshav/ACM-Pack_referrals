import re
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Profile
from chat.models import Conversation

from .models import ConnectionRequest, ReferralRequest

User = get_user_model()


def seed():
    """Run the command and return its "name: value" lines as a dict."""
    out = StringIO()
    call_command("seed_demo_data", stdout=out)
    return dict(re.findall(r"^([a-z_]+): (\S+)$", out.getvalue(), re.MULTILINE))


@override_settings(DEBUG=True)
class SeedDemoDataTests(TestCase):
    """The Postman collection depends on these fixtures being usable and repeatable."""

    def test_refuses_to_run_without_debug(self):
        with override_settings(DEBUG=False):
            self.assertEqual(seed(), {})
        self.assertFalse(User.objects.filter(username="postman_sender").exists())

    def test_seeded_members_are_active(self):
        # The directory and referral asks both ignore unverified members.
        values = seed()
        for key in ("sender_id", "recipient_id", "outsider_id"):
            profile = Profile.objects.get(user_id=values[key])
            self.assertEqual(profile.account_status, Profile.AccountStatus.ACTIVE)

    def test_printed_code_verifies_the_test_account(self):
        values = seed()
        response = APIClient().post(
            "/api/accounts/auth/verify/",
            {"email": values["verify_email"], "code": values["verify_code"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_signup_address_is_free(self):
        values = seed()
        self.assertFalse(User.objects.filter(email=values["signup_email"]).exists())

    def test_second_run_clears_the_first_runs_rows(self):
        values = seed()
        sender = User.objects.get(pk=values["sender_id"])
        recipient = User.objects.get(pk=values["recipient_id"])
        client = APIClient()
        client.force_authenticate(sender)
        connection = ConnectionRequest.objects.create(
            sender=sender, recipient=recipient, status=ConnectionRequest.Status.ACCEPTED
        )
        conversation = Conversation.objects.create(created_from_connection_request=connection)
        conversation.participants.add(sender, recipient)
        response = client.post(
            "/api/connections/referrals/",
            {
                "recipient_id": recipient.pk,
                "company_id": int(values["company_id"]),
                "role_title": "SWE Intern",
                "contact_email": "sender@example.com",
                "message_text": "Hi",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

        again = seed()

        self.assertEqual(again["sender_id"], values["sender_id"])
        self.assertFalse(ConnectionRequest.objects.exists())
        self.assertFalse(ReferralRequest.objects.exists())
        self.assertFalse(Conversation.objects.exists())
