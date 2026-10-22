from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from chat.models import Conversation
from chat.services import ConversationAlreadyExistsError

from .models import ConnectionRequest
from .services import (
    ConnectionActionError,
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

    def test_accept_rolls_back_status_if_conversation_already_exists(self):
        with mock.patch(
            "connections.services.create_conversation_from_request",
            side_effect=ConversationAlreadyExistsError("exists"),
        ):
            # A conflict: reported as 409, not as bad input.
            with self.assertRaises(RequestNotPendingError):
                accept_connection_request(self.request.pk, self.recipient)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ConnectionRequest.Status.PENDING)
        self.assertIsNone(self.request.resolved_at)

    def test_accept_maps_other_conversation_errors_to_400_not_409(self):
        with mock.patch(
            "connections.services.create_conversation_from_request",
            side_effect=ValueError("Cannot create a conversation with yourself."),
        ):
            with self.assertRaises(ConnectionActionError) as caught:
                accept_connection_request(self.request.pk, self.recipient)
        self.assertNotIsInstance(caught.exception, RequestNotPendingError)
        self.assertEqual(caught.exception.status_code, 400)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ConnectionRequest.Status.PENDING)

    def test_accept_of_a_request_to_yourself_is_a_400(self):
        # The API blocks these, but admin or a seed command can create one.
        self_request = ConnectionRequest.objects.create(
            sender=self.recipient, recipient=self.recipient, message_text="me"
        )
        with self.assertRaises(ConnectionActionError) as caught:
            accept_connection_request(self_request.pk, self.recipient)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(Conversation.objects.count(), 0)

    # races: the loser must get a 409 and must not overwrite the winner

    def test_decline_loses_to_an_accept_that_lands_first(self):
        # Both calls pass the up-front pending check; the accept resolves in between.
        real_lookup = decline_connection_request.__globals__["_get_request_for_recipient"]

        competing = {"started": False}

        def lookup_then_accept(connection_id, user):
            found = real_lookup(connection_id, user)
            if not competing["started"]:
                competing["started"] = True
                accept_connection_request(connection_id, self.recipient)
            return found

        with mock.patch(
            "connections.services._get_request_for_recipient", side_effect=lookup_then_accept
        ):
            with self.assertRaises(RequestNotPendingError):
                decline_connection_request(self.request.pk, self.recipient)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ConnectionRequest.Status.ACCEPTED)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_accept_loses_to_a_decline_that_lands_first(self):
        real_lookup = accept_connection_request.__globals__["_get_request_for_recipient"]

        competing = {"started": False}

        def lookup_then_decline(connection_id, user):
            found = real_lookup(connection_id, user)
            if not competing["started"]:
                competing["started"] = True
                decline_connection_request(connection_id, self.recipient)
            return found

        with mock.patch(
            "connections.services._get_request_for_recipient", side_effect=lookup_then_decline
        ):
            with self.assertRaises(RequestNotPendingError):
                accept_connection_request(self.request.pk, self.recipient)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ConnectionRequest.Status.DECLINED)
        self.assertEqual(Conversation.objects.count(), 0)

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
