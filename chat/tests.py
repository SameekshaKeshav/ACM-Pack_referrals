from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from connections.models import ConnectionRequest

from .models import Conversation, ConversationParticipant, Message
from .services import create_conversation_from_request

User = get_user_model()


class CreateConversationFromRequestTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username="sender",
            email="sender@ncsu.edu",
            password="pass",
        )
        self.recipient = User.objects.create_user(
            username="recipient",
            email="recipient@ncsu.edu",
            password="pass",
        )

    def test_creates_conversation_with_two_participants(self):
        request = ConnectionRequest.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            status=ConnectionRequest.Status.ACCEPTED,
        )

        conversation = create_conversation_from_request(request)

        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(conversation.conversation_participants.count(), 2)
        participant_user_ids = set(
            conversation.conversation_participants.values_list("user_id", flat=True)
        )
        self.assertEqual(participant_user_ids, {self.sender.pk, self.recipient.pk})
        self.assertEqual(
            conversation.created_from_connection_request_id,
            request.pk,
        )

    def test_rejects_non_accepted_request(self):
        request = ConnectionRequest.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            status=ConnectionRequest.Status.PENDING,
        )

        with self.assertRaises(ValueError):
            create_conversation_from_request(request)

        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(ConversationParticipant.objects.count(), 0)

    def test_rejects_a_request_sent_to_yourself(self):
        request = ConnectionRequest.objects.create(
            sender=self.sender,
            recipient=self.sender,
            status=ConnectionRequest.Status.ACCEPTED,
        )

        with self.assertRaises(ValueError):
            create_conversation_from_request(request)

        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(ConversationParticipant.objects.count(), 0)

    def test_second_call_for_the_same_request_raises_value_error(self):
        request = ConnectionRequest.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            status=ConnectionRequest.Status.ACCEPTED,
        )
        create_conversation_from_request(request)

        with self.assertRaises(ValueError):
            create_conversation_from_request(request)

        self.assertEqual(Conversation.objects.count(), 1)

    def test_losing_a_concurrent_accept_raises_value_error_not_integrity_error(self):
        """Two accepts can both pass the exists() check; the DB constraint then
        rejects the loser, which must still surface as ValueError."""
        request = ConnectionRequest.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            status=ConnectionRequest.Status.ACCEPTED,
        )
        create_conversation_from_request(request)

        # Simulate the race: the pre-check wrongly reports "no conversation yet".
        with mock.patch.object(
            Conversation.objects,
            "filter",
            return_value=mock.Mock(exists=mock.Mock(return_value=False)),
        ):
            with self.assertRaises(ValueError):
                create_conversation_from_request(request)

        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(ConversationParticipant.objects.count(), 2)


class MessageBodyLengthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="author", email="author@ncsu.edu", password="pass"
        )
        self.conversation = Conversation.objects.create()

    def test_accepts_a_body_of_exactly_2000_characters(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.user,
            body_text="x" * 2000,
        )
        self.assertEqual(len(message.body_text), 2000)

    def test_database_rejects_a_body_over_2000_characters(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Message.objects.create(
                conversation=self.conversation,
                sender=self.user,
                body_text="x" * 2001,
            )
        self.assertEqual(Message.objects.count(), 0)
