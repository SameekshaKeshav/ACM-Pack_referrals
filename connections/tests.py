from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Profile
from companies.models import Company
from connections.models import ConnectionRequest


User = get_user_model()


class ConnectionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sender = User.objects.create_user(
            username="sender",
            first_name="Sender",
            last_name="User",
        )
        self.recipient = User.objects.create_user(
            username="recipient",
        )
        self.company = Company.objects.create(name="Acme")
        Profile.objects.create(
            user=self.sender,
            current_company=self.company,
            open_to_connect=True,
        )
        Profile.objects.create(
            user=self.recipient,
            current_company=self.company,
            open_to_connect=True,
        )
        self.authenticate(self.sender)

    def authenticate(self, user):
        token = AccessToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

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

    def test_incoming_connections_list(self):
        self.client.post(
            "/api/connections/",
            {"recipient": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.authenticate(self.recipient)
        response = self.client.get("/api/connections/?type=incoming")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["sender"], {"name": "Sender User", "company": "Acme"})
        self.assertEqual(
            set(response.json()[0]),
            {"id", "sender", "message_text", "status", "created_at"},
        )

    def test_incoming_connections_list_only_includes_pending_requests(self):
        ConnectionRequest.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            status=ConnectionRequest.Status.ACCEPTED,
        )

        self.authenticate(self.recipient)
        response = self.client.get("/api/connections/?type=incoming")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_outgoing_connections_list(self):
        self.client.post(
            "/api/connections/",
            {"recipient": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        response = self.client.get("/api/connections/?type=outgoing")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["recipient"], {
            "id": self.recipient.pk,
            "name": "recipient",
            "company": "Acme",
        })

    def test_accept_connection_request(self: TestCase) -> None:
        response = self.client.patch(
            "/api/connections/123/accept/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 501)

    def test_connection_request_detail_actions_are_not_exposed(self):
        connection_request = self.client.post(
            "/api/connections/",
            {"recipient": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.assertEqual(
            self.client.delete(
                f"/api/connections/{connection_request.json()['id']}/"
            ).status_code,
            404,
        )

    def test_request_to_self_returns_bad_request(self):
        response = self.client.post(
            "/api/connections/",
            {"recipient": self.sender.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_duplicate_pending_request_in_either_direction_returns_conflict(self):
        ConnectionRequest.objects.create(
            sender=self.recipient,
            recipient=self.sender,
            status=ConnectionRequest.Status.PENDING,
        )

        response = self.client.post(
            "/api/connections/",
            {"recipient": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 409)

    def test_closed_recipient_returns_forbidden(self):
        Profile.objects.filter(user=self.recipient).update(open_to_connect=False)

        response = self.client.post(
            "/api/connections/",
            {"recipient": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_message_text_longer_than_500_returns_bad_request(self):
        response = self.client.post(
            "/api/connections/",
            {"recipient": self.recipient.pk, "message_text": "x" * 501},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_access_is_rejected(self):
        self.client.credentials()

        response = self.client.get("/api/connections/?type=outgoing")

        self.assertIn(response.status_code, (401, 403))
