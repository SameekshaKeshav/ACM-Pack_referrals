from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from chat.services import create_conversation_from_request

from .blocks import blocked_user_ids
from .models import Block, ConnectionRequest
from .serializers import ConnectionRequestDetailSerializer

User = get_user_model()


class BlockModelTests(TestCase):
    """The sample Block model. BE2 may replace it; blocked_user_ids() is the contract."""

    def setUp(self):
        self.alice = User.objects.create_user(username="alice")
        self.bob = User.objects.create_user(username="bob")
        self.carol = User.objects.create_user(username="carol")

    def test_a_user_cannot_block_themselves(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Block.objects.create(blocker=self.alice, blocked=self.alice)

    def test_the_same_block_cannot_be_stored_twice(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Block.objects.create(blocker=self.alice, blocked=self.bob)

    def test_blocking_in_both_directions_is_two_separate_rows(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        Block.objects.create(blocker=self.bob, blocked=self.alice)

        self.assertEqual(Block.objects.count(), 2)

    def test_blocked_user_ids_covers_both_directions_and_excludes_the_user(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        Block.objects.create(blocker=self.carol, blocked=self.alice)

        self.assertEqual(blocked_user_ids(self.alice), {self.bob.pk, self.carol.pk})
        self.assertEqual(blocked_user_ids(self.bob), {self.alice.pk})

    def test_blocked_user_ids_is_empty_without_blocks_and_is_one_query(self):
        with self.assertNumQueries(1):
            self.assertEqual(blocked_user_ids(self.alice), set())


class ConversationIdQueryTests(TestCase):
    """The detail serializer must not run one conversation query per request."""

    def setUp(self):
        self.me = User.objects.create_user(username="me")
        self.requests = []
        for index in range(5):
            other = User.objects.create_user(username=f"other{index}")
            request = ConnectionRequest.objects.create(
                sender=self.me, recipient=other, status=ConnectionRequest.Status.ACCEPTED
            )
            create_conversation_from_request(request)
            self.requests.append(request)

    def queryset(self):
        return ConnectionRequest.objects.select_related(
            "sender__profile__current_company",
            "recipient__profile__current_company",
            "conversation",
        ).order_by("pk")

    def test_a_list_costs_a_constant_number_of_queries(self):
        # Rows, plus nothing per request for conversation_id.
        with self.assertNumQueries(1):
            data = ConnectionRequestDetailSerializer(self.queryset(), many=True).data

        self.assertEqual(len(data), 5)

    def test_conversation_ids_are_correct_in_a_list(self):
        data = ConnectionRequestDetailSerializer(self.queryset(), many=True).data

        for row, request in zip(data, self.requests):
            self.assertEqual(row["conversation_id"], request.conversation.pk)

    def test_requests_without_a_conversation_have_none(self):
        pending = ConnectionRequest.objects.create(sender=self.me, recipient=self.me)

        rows = self.queryset().filter(pk=pending.pk)
        data = ConnectionRequestDetailSerializer(rows, many=True).data

        self.assertIsNone(data[0]["conversation_id"])

    def test_it_still_works_without_select_related(self):
        data = ConnectionRequestDetailSerializer(self.requests[0]).data

        self.assertEqual(data["conversation_id"], self.requests[0].conversation.pk)
