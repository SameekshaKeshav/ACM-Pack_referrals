from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from chat.models import Conversation

from .models import ConnectionRequest
from .services import (
    NotRecipientError,
    RequestNotPendingError,
    accept_connection_request,
    decline_connection_request,
)

User = get_user_model()


class ConnectionServiceTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(username="sender", password="x")
        self.recipient = User.objects.create_user(username="recipient", password="x")
        self.outsider = User.objects.create_user(username="outsider", password="x")
        self.request = ConnectionRequest.objects.create(
            sender=self.sender, recipient=self.recipient, message_text="hi"
        )

    # accept

    def test_accept_creates_conversation_and_marks_accepted(self):
        connection_request, conversation = accept_connection_request(
            self.request.pk, self.recipient
        )

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ConnectionRequest.Status.ACCEPTED)
        self.assertIsNotNone(self.request.resolved_at)
        self.assertEqual(connection_request.pk, self.request.pk)
        self.assertEqual(conversation.created_from_connection_request, self.request)
        self.assertCountEqual(
            conversation.participants.all(), [self.sender, self.recipient]
        )

    def test_accept_twice_is_rejected_without_second_conversation(self):
        accept_connection_request(self.request.pk, self.recipient)
        with self.assertRaises(RequestNotPendingError):
            accept_connection_request(self.request.pk, self.recipient)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_accept_by_sender_is_forbidden(self):
        with self.assertRaises(NotRecipientError):
            accept_connection_request(self.request.pk, self.sender)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ConnectionRequest.Status.PENDING)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_accept_by_outsider_looks_like_not_found(self):
        with self.assertRaises(ConnectionRequest.DoesNotExist):
            accept_connection_request(self.request.pk, self.outsider)

    def test_accept_unknown_id_not_found(self):
        with self.assertRaises(ConnectionRequest.DoesNotExist):
            accept_connection_request(9999, self.recipient)

    def test_accept_declined_request_rejected(self):
        decline_connection_request(self.request.pk, self.recipient)
        with self.assertRaises(RequestNotPendingError):
            accept_connection_request(self.request.pk, self.recipient)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_accept_rolls_back_status_if_conversation_creation_fails(self):
        with mock.patch(
            "connections.services.create_conversation_from_request",
            side_effect=ValueError("boom"),
        ):
            with self.assertRaises(RequestNotPendingError):
                accept_connection_request(self.request.pk, self.recipient)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ConnectionRequest.Status.PENDING)
        self.assertIsNone(self.request.resolved_at)

    # decline

    def test_decline_sets_status_and_creates_no_conversation(self):
        result = decline_connection_request(self.request.pk, self.recipient)

        self.request.refresh_from_db()
        self.assertEqual(result.pk, self.request.pk)
        self.assertEqual(self.request.status, ConnectionRequest.Status.DECLINED)
        self.assertIsNotNone(self.request.resolved_at)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_decline_by_sender_is_forbidden(self):
        with self.assertRaises(NotRecipientError):
            decline_connection_request(self.request.pk, self.sender)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ConnectionRequest.Status.PENDING)

    def test_decline_by_outsider_looks_like_not_found(self):
        with self.assertRaises(ConnectionRequest.DoesNotExist):
            decline_connection_request(self.request.pk, self.outsider)

    def test_decline_already_accepted_rejected(self):
        accept_connection_request(self.request.pk, self.recipient)
        with self.assertRaises(RequestNotPendingError):
            decline_connection_request(self.request.pk, self.recipient)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ConnectionRequest.Status.ACCEPTED)
