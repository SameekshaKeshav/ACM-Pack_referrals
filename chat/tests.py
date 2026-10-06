from django.contrib.auth import get_user_model
from django.test import TestCase

from connections.models import ConnectionRequest

from .models import Conversation, ConversationParticipant
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
