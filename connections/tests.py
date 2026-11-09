from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Profile
from companies.models import Company
from connections.models import Block, ConnectionRequest


User = get_user_model()


class ConnectionTests(APITestCase):
    def setUp(self):
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

    def test_create_request(self):
        payload = {"recipient_id": self.recipient.pk, "message_text": "Hello"}
        response = self.client.post("/api/connections/", payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id"], 1)
        self.assertEqual(response.json()["status"], ConnectionRequest.Status.PENDING)

    def test_create_duplicate_request(self):
        payload = {"recipient_id": self.recipient.pk, "message_text": "Hello"}

        self.assertEqual(
            self.client.post("/api/connections/", payload, format="json").status_code,
            201,
        )
        self.assertEqual(
            self.client.post("/api/connections/", payload, format="json").status_code,
            409,
        )

    def test_block_user(self):
        response = self.client.post(
            f"/api/connections/users/{self.recipient.pk}/block/"
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Block.objects.filter(
                blocker=self.sender,
                blocked=self.recipient,
            ).exists()
        )

    def test_block_user_is_idempotent(self):
        url = f"/api/connections/users/{self.recipient.pk}/block/"

        self.assertEqual(self.client.post(url).status_code, 201)
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(Block.objects.count(), 1)

    def test_unblock_user(self):
        Block.objects.create(blocker=self.sender, blocked=self.recipient)

        response = self.client.delete(
            f"/api/connections/users/{self.recipient.pk}/block/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Block.objects.exists())

    def test_blocked_pair_cannot_create_connection_in_either_direction(self):
        Block.objects.create(blocker=self.recipient, blocked=self.sender)

        response = self.client.post(
            "/api/connections/",
            {"recipient_id": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ConnectionRequest.objects.exists())

    def test_block_unknown_user_returns_not_found(self):
        response = self.client.post(
            "/api/connections/users/9999/block/"
        )

        self.assertEqual(response.status_code, 404)

    def test_incoming_connections_list(self):
        self.client.post(
            "/api/connections/",
            {"recipient_id": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.authenticate(self.recipient)
        response = self.client.get("/api/connections/?type=incoming")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["sender"], {
            "id": self.sender.pk,
            "name": "Sender User",
            "company": "Acme",
        })
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
            {"recipient_id": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        response = self.client.get("/api/connections/?type=outgoing")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["recipient"], {
            "id": self.recipient.pk,
            "name": "recipient",
            "company": "Acme",
        })

    def test_connection_request_endpoint_is_not_exposed(self):
        self.assertEqual(
            self.client.get(
                "/api/connections/connection-requests"
            ).status_code,
            404,
        )

    def test_request_to_self_returns_bad_request(self):
        response = self.client.post(
            "/api/connections/",
            {"recipient_id": self.sender.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_unknown_recipient_returns_not_found(self):
        response = self.client.post(
            "/api/connections/",
            {"recipient_id": self.recipient.pk + 1, "message_text": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_duplicate_pending_request_in_either_direction_returns_conflict(self):
        ConnectionRequest.objects.create(
            sender=self.recipient,
            recipient=self.sender,
            status=ConnectionRequest.Status.PENDING,
        )

        response = self.client.post(
            "/api/connections/",
            {"recipient_id": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 409)

    def test_existing_connection_returns_conflict(self):
        ConnectionRequest.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            status=ConnectionRequest.Status.ACCEPTED,
        )

        response = self.client.post(
            "/api/connections/",
            {"recipient_id": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 409)

    def test_declined_pair_returns_forbidden_and_is_hidden_from_outgoing_list(self):
        ConnectionRequest.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            status=ConnectionRequest.Status.DECLINED,
        )

        response = self.client.post(
            "/api/connections/",
            {"recipient_id": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        response = self.client.get("/api/connections/?type=outgoing")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_closed_recipient_returns_forbidden(self):
        self.assertTrue(self.recipient.profile.open_to_connect)
        Profile.objects.filter(user=self.recipient).update(open_to_connect=False)

        response = self.client.post(
            "/api/connections/",
            {"recipient_id": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"],
            "This user is not open to connection requests.",
        )
        self.assertFalse(ConnectionRequest.objects.exists())

    def test_suspended_recipient_returns_forbidden(self):
        Profile.objects.filter(user=self.recipient).update(account_status="suspended")

        response = self.client.post(
            "/api/connections/",
            {"recipient_id": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_message_preserves_intentional_whitespace(self):
        response = self.client.post(
            "/api/connections/",
            {"recipient_id": self.recipient.pk, "message_text": "  Hello  "},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            ConnectionRequest.objects.get(pk=response.json()["id"]).message_text,
            "  Hello  ",
        )

    def test_recipient_id_must_be_a_positive_json_integer(self):
        for recipient_id in (0, -1, "1", True):
            with self.subTest(recipient_id=recipient_id):
                response = self.client.post(
                    "/api/connections/",
                    {"recipient_id": recipient_id, "message_text": "Hello"},
                    format="json",
                )

                self.assertEqual(response.status_code, 400)

    def test_exceeding_request_rate_limit(self):
        ConnectionRequest.objects.bulk_create(
            [
                ConnectionRequest(
                    sender=self.sender,
                    recipient=self.recipient,
                    message_text=f"Hello {index}",
                    created_at=timezone.now() - timedelta(hours=1),
                )
                for index in range(10)
            ]
        )

        other_recipient = User.objects.create_user(username="other-recipient")
        Profile.objects.create(user=other_recipient, open_to_connect=True)
        response = self.client.post(
            "/api/connections/",
            {"recipient_id": other_recipient.pk, "message_text": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 429)

    def test_message_text_longer_than_500_returns_bad_request(self):
        response = self.client.post(
            "/api/connections/",
            {"recipient_id": self.recipient.pk, "message_text": "x" * 501},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_access_is_rejected(self):
        self.client.credentials()

        response = self.client.get("/api/connections/?type=outgoing")

        self.assertIn(response.status_code, (401, 403))
