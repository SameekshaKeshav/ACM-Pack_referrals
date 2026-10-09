from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Profile
from companies.models import Company


User = get_user_model()


class ConnectionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sender = User.objects.create_user(
            username="sender",
            first_name="Sender",
            last_name="User",
        )
        self.recipient = User.objects.create_user(username="recipient")
        self.company = Company.objects.create(name="Acme")
        Profile.objects.create(
            user=self.sender,
            current_company=self.company,
            open_to_connect=True,
        )
        Profile.objects.create(user=self.recipient, open_to_connect=True)
        self.client.force_authenticate(user=self.sender)

    def test_create_duplicate_request(self):
        payload = {"recipient": self.recipient.pk, "message_text": "Hello"}

        self.assertEqual(
            self.client.post("/api/connections/", payload, format="json").status_code,
            201,
        )
        self.assertEqual(
            self.client.post("/api/connections/", payload, format="json").status_code,
            409,
        )

    def test_incoming_connection_list(self):
        self.client.post(
            "/api/connections/",
            {"recipient": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.client.force_authenticate(user=self.recipient)
        response = self.client.get("/api/connections/?type=incoming")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["sender"], {"name": "Sender User", "company": "Acme"})
        self.assertEqual(
            set(response.json()[0]),
            {"id", "sender", "message_text", "status", "created_at"},
        )

    def test_accept_connection_request(self: TestCase) -> None:
        response = self.client.patch(
            "/api/connections/123/accept/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 501)
