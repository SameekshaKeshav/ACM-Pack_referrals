from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Profile
from chat.models import Conversation
from companies.models import Company

from .models import ConnectionRequest

User = get_user_model()


class ConnectionActionEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        company = Company.objects.create(name="Acme")
        self.sender = self._user("sender")
        self.recipient = self._user("recipient")
        self.outsider = self._user("outsider")
        for user in (self.sender, self.recipient, self.outsider):
            Profile.objects.create(user=user, current_company=company, open_to_connect=True)

    def _user(self, username):
        return User.objects.create_user(username=username)

    def _as(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def _create_pending(self):
        self._as(self.sender)
        response = self.client.post(
            "/api/connections/",
            {"recipient_id": self.recipient.pk, "message_text": "Hello"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def _accept_url(self, pk):
        return f"/api/connections/{pk}/accept/"

    def _decline_url(self, pk):
        return f"/api/connections/{pk}/decline/"

    # the Week 5 deliverable: accept -> 200 + real conversation_id -> GET shows accepted

    def test_accept_returns_conversation_id_and_detail_shows_accepted(self):
        pk = self._create_pending()

        self._as(self.recipient)
        response = self.client.patch(self._accept_url(pk))
        self.assertEqual(response.status_code, 200)
        conversation_id = response.json()["conversation_id"]
        self.assertEqual(list(response.json()), ["conversation_id"])
        conversation = Conversation.objects.get(pk=conversation_id)
        self.assertEqual(conversation.created_from_connection_request_id, pk)
        self.assertCountEqual(
            conversation.participants.all(), [self.sender, self.recipient]
        )

        detail = self.client.get(f"/api/connections/{pk}/")
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["status"], "accepted")
        self.assertEqual(body["conversation_id"], conversation_id)
        self.assertIsNotNone(body["resolved_at"])
        self.assertEqual(body["sender"]["id"], self.sender.pk)
        self.assertEqual(body["recipient"]["id"], self.recipient.pk)

    def test_sender_can_also_read_the_accepted_request(self):
        pk = self._create_pending()
        self._as(self.recipient)
        self.client.patch(self._accept_url(pk))

        self._as(self.sender)
        response = self.client.get(f"/api/connections/{pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "accepted")

    def test_decline_sets_declined_and_creates_no_conversation(self):
        pk = self._create_pending()

        self._as(self.recipient)
        response = self.client.patch(self._decline_url(pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": pk, "status": "declined"})
        self.assertEqual(Conversation.objects.count(), 0)

        detail = self.client.get(f"/api/connections/{pk}/").json()
        self.assertEqual(detail["status"], "declined")
        self.assertIsNone(detail["conversation_id"])

    def test_pending_detail_has_no_conversation_or_resolved_at(self):
        pk = self._create_pending()
        body = self.client.get(f"/api/connections/{pk}/").json()
        self.assertEqual(body["status"], "pending")
        self.assertIsNone(body["conversation_id"])
        self.assertIsNone(body["resolved_at"])

    # guards

    def test_accept_twice_returns_conflict(self):
        pk = self._create_pending()
        self._as(self.recipient)
        self.assertEqual(self.client.patch(self._accept_url(pk)).status_code, 200)
        self.assertEqual(self.client.patch(self._accept_url(pk)).status_code, 409)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_accept_after_decline_returns_conflict(self):
        pk = self._create_pending()
        self._as(self.recipient)
        self.client.patch(self._decline_url(pk))
        self.assertEqual(self.client.patch(self._accept_url(pk)).status_code, 409)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_decline_after_accept_returns_conflict(self):
        pk = self._create_pending()
        self._as(self.recipient)
        self.client.patch(self._accept_url(pk))
        self.assertEqual(self.client.patch(self._decline_url(pk)).status_code, 409)
        self.assertEqual(
            ConnectionRequest.objects.get(pk=pk).status,
            ConnectionRequest.Status.ACCEPTED,
        )

    def test_sender_cannot_accept_or_decline(self):
        pk = self._create_pending()
        for url in (self._accept_url(pk), self._decline_url(pk)):
            with self.subTest(url=url):
                self._as(self.sender)
                self.assertEqual(self.client.patch(url).status_code, 403)
        self.assertEqual(
            ConnectionRequest.objects.get(pk=pk).status,
            ConnectionRequest.Status.PENDING,
        )
        self.assertEqual(Conversation.objects.count(), 0)

    def test_outsider_gets_not_found_for_everything(self):
        pk = self._create_pending()
        self._as(self.outsider)
        self.assertEqual(self.client.patch(self._accept_url(pk)).status_code, 404)
        self.assertEqual(self.client.patch(self._decline_url(pk)).status_code, 404)
        self.assertEqual(self.client.get(f"/api/connections/{pk}/").status_code, 404)

    def test_unknown_id_returns_not_found(self):
        self._as(self.recipient)
        self.assertEqual(self.client.patch(self._accept_url(9999)).status_code, 404)
        self.assertEqual(self.client.patch(self._decline_url(9999)).status_code, 404)
        self.assertEqual(self.client.get("/api/connections/9999/").status_code, 404)

    def test_anonymous_is_rejected(self):
        pk = self._create_pending()
        self.client.credentials()
        self.assertEqual(self.client.patch(self._accept_url(pk)).status_code, 401)
        self.assertEqual(self.client.patch(self._decline_url(pk)).status_code, 401)
        self.assertEqual(self.client.get(f"/api/connections/{pk}/").status_code, 401)

    def test_only_patch_is_allowed_on_accept_and_decline(self):
        pk = self._create_pending()
        self._as(self.recipient)
        for url in (self._accept_url(pk), self._decline_url(pk)):
            for method in ("get", "post", "put", "delete"):
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url)
                    self.assertEqual(response.status_code, 405)

    def test_detail_is_read_only(self):
        pk = self._create_pending()
        for method in ("patch", "put", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(f"/api/connections/{pk}/")
                self.assertEqual(response.status_code, 405)
