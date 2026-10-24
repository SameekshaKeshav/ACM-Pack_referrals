from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from unittest import mock

from django.core.cache import cache

from accounts.models import Profile
from companies.models import Company
from connections.models import Block, ConnectionRequest

from .models import Conversation, ConversationParticipant, Message
from .services import create_conversation_from_request
from .throttling import MessageSendThrottle

User = get_user_model()


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


class ChatApiTestCase(TestCase):
    """Alice and Bob share a conversation; Carol is a logged-in outsider."""

    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name="Acme")
        cls.alice = User.objects.create_user(
            username="alice", email="alice@ncsu.edu", first_name="Alice", last_name="A"
        )
        cls.bob = User.objects.create_user(
            username="bob", email="bob@ncsu.edu", first_name="Bob", last_name="B"
        )
        cls.carol = User.objects.create_user(username="carol", email="carol@ncsu.edu")
        Profile.objects.create(user=cls.bob, current_company=company)
        request = ConnectionRequest.objects.create(
            sender=cls.alice,
            recipient=cls.bob,
            status=ConnectionRequest.Status.ACCEPTED,
        )
        cls.conversation = create_conversation_from_request(request)

    def send(self, sender, body, conversation=None, offset_seconds=0):
        message = Message.objects.create(
            conversation=conversation or self.conversation, sender=sender, body_text=body
        )
        if offset_seconds:
            Message.objects.filter(pk=message.pk).update(
                created_at=timezone.now() + timedelta(seconds=offset_seconds)
            )
            message.refresh_from_db()
        return message

    def messages_url(self, conversation=None):
        return f"/api/chat/conversations/{(conversation or self.conversation).pk}/messages/"


class ConversationListTests(ChatApiTestCase):
    def test_requires_authentication(self):
        self.assertEqual(APIClient().get("/api/chat/conversations/").status_code, 401)

    def test_lists_only_my_conversations_with_the_other_person(self):
        response = client_for(self.alice).get("/api/chat/conversations/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["id"], self.conversation.pk)
        self.assertEqual(
            body[0]["other_user"], {"id": self.bob.pk, "name": "Bob B", "company": "Acme"}
        )

    def test_the_other_participant_sees_me_as_the_other_user(self):
        body = client_for(self.bob).get("/api/chat/conversations/").json()

        self.assertEqual(body[0]["other_user"]["id"], self.alice.pk)
        self.assertEqual(body[0]["other_user"]["name"], "Alice A")
        self.assertIsNone(body[0]["other_user"]["company"])

    def test_outsider_sees_an_empty_list(self):
        self.assertEqual(client_for(self.carol).get("/api/chat/conversations/").json(), [])

    def test_empty_conversation_has_no_last_message(self):
        body = client_for(self.alice).get("/api/chat/conversations/").json()

        self.assertIsNone(body[0]["last_message"])
        self.assertEqual(body[0]["unread_count"], 0)

    def test_last_message_preview_and_unread_count(self):
        self.send(self.alice, "first", offset_seconds=-30)
        self.send(self.bob, "second", offset_seconds=-20)
        last = self.send(self.bob, "third", offset_seconds=-10)

        alice_row = client_for(self.alice).get("/api/chat/conversations/").json()[0]
        bob_row = client_for(self.bob).get("/api/chat/conversations/").json()[0]

        self.assertEqual(alice_row["last_message"]["id"], last.pk)
        self.assertEqual(alice_row["last_message"]["body_text"], "third")
        self.assertEqual(alice_row["last_message"]["sender_id"], self.bob.pk)
        # Unread counts only unread messages from the other person.
        self.assertEqual(alice_row["unread_count"], 2)
        self.assertEqual(bob_row["unread_count"], 1)

    def test_sorted_by_latest_activity_then_newest_first(self):
        other_request = ConnectionRequest.objects.create(
            sender=self.alice,
            recipient=self.carol,
            status=ConnectionRequest.Status.ACCEPTED,
        )
        newer = create_conversation_from_request(other_request)
        self.send(self.bob, "old", conversation=self.conversation, offset_seconds=-100)
        self.send(self.carol, "recent", conversation=newer, offset_seconds=-5)

        ids = [row["id"] for row in client_for(self.alice).get("/api/chat/conversations/").json()]

        self.assertEqual(ids, [newer.pk, self.conversation.pk])

    def test_query_count_does_not_grow_with_conversations(self):
        client = client_for(self.alice)
        # the user, the block lookup, the conversation rows, and the participants
        with self.assertNumQueries(4):
            client.get("/api/chat/conversations/")
        for index in range(4):
            other = User.objects.create_user(username=f"extra{index}", email=f"e{index}@ncsu.edu")
            request = ConnectionRequest.objects.create(
                sender=self.alice, recipient=other, status=ConnectionRequest.Status.ACCEPTED
            )
            conversation = create_conversation_from_request(request)
            self.send(other, "hi", conversation=conversation)
        with self.assertNumQueries(4):
            client.get("/api/chat/conversations/")


class ConversationMessagesTests(ChatApiTestCase):
    def test_requires_authentication(self):
        self.assertEqual(APIClient().get(self.messages_url()).status_code, 401)

    def test_participant_reads_their_messages_oldest_first(self):
        first = self.send(self.alice, "hello", offset_seconds=-20)
        second = self.send(self.bob, "hi", offset_seconds=-10)

        response = client_for(self.alice).get(self.messages_url())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([m["id"] for m in body], [first.pk, second.pk])
        self.assertEqual(
            set(body[0]),
            {"id", "conversation_id", "sender_id", "body_text", "created_at", "read_status"},
        )
        self.assertEqual(body[0]["sender_id"], self.alice.pk)

    def test_outsider_gets_403(self):
        self.send(self.alice, "private")

        response = client_for(self.carol).get(self.messages_url())

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("private", response.content.decode())

    def test_unknown_conversation_is_404(self):
        response = client_for(self.alice).get("/api/chat/conversations/9999/messages/")

        self.assertEqual(response.status_code, 404)

    def test_empty_conversation_returns_an_empty_list(self):
        self.assertEqual(client_for(self.alice).get(self.messages_url()).json(), [])

    def test_default_returns_the_latest_page_oldest_first(self):
        sent = [self.send(self.alice, f"m{i}", offset_seconds=i - 100) for i in range(5)]

        body = client_for(self.alice).get(self.messages_url() + "?limit=3").json()

        self.assertEqual([m["id"] for m in body], [m.pk for m in sent[2:]])

    def test_poll_returns_only_newer_messages_ascending(self):
        sent = [self.send(self.alice, f"m{i}", offset_seconds=i - 100) for i in range(4)]

        body = client_for(self.bob).get(self.messages_url() + f"?after={sent[1].pk}").json()

        self.assertEqual([m["id"] for m in body], [sent[2].pk, sent[3].pk])

    def test_poll_with_nothing_new_returns_an_empty_list(self):
        last = self.send(self.alice, "only")

        body = client_for(self.bob).get(self.messages_url() + f"?after={last.pk}").json()

        self.assertEqual(body, [])

    def test_poll_respects_limit(self):
        sent = [self.send(self.alice, f"m{i}") for i in range(4)]

        body = client_for(self.bob).get(self.messages_url() + f"?after={sent[0].pk}&limit=2").json()

        self.assertEqual([m["id"] for m in body], [sent[1].pk, sent[2].pk])

    def test_older_history_uses_an_exclusive_created_at_and_id_cursor(self):
        same_time = timezone.now() - timedelta(minutes=5)
        tied = [self.send(self.alice, f"t{i}") for i in range(3)]
        Message.objects.filter(pk__in=[m.pk for m in tied]).update(created_at=same_time)
        older = self.send(self.alice, "older", offset_seconds=-600)
        stamp = same_time.isoformat().replace("+00:00", "Z")

        client = client_for(self.alice)
        body = client.get(self.messages_url() + f"?before={stamp}&before_id={tied[2].pk}").json()

        # Messages tied at the cursor time are included only if their id is lower.
        self.assertEqual([m["id"] for m in body], [older.pk, tied[0].pk, tied[1].pk])

    def test_invalid_parameters_are_400(self):
        client = client_for(self.alice)
        stamp = "2026-10-07T14:34:00Z"
        for query in (
            "?limit=0",
            "?limit=101",
            "?limit=abc",
            "?after=abc",
            "?after=-1",
            f"?before={stamp}",  # needs before_id
            "?before_id=5",  # needs before
            f"?before={stamp}&before_id=5&after=1",  # both cursors
            "?before=not-a-date&before_id=5",
            "?before=2026-10-07T14:34:00&before_id=5",  # naive timestamp
        ):
            with self.subTest(query=query):
                self.assertEqual(client.get(self.messages_url() + query).status_code, 400)

    def test_fetching_does_not_mark_messages_read(self):
        self.send(self.alice, "hello")

        client_for(self.bob).get(self.messages_url())

        self.assertFalse(Message.objects.get().read_status)


class SendMessageTests(ChatApiTestCase):
    def post(self, user, payload):
        return client_for(user).post("/api/chat/messages/", payload, format="json")

    def test_requires_authentication(self):
        response = APIClient().post(
            "/api/chat/messages/",
            {"conversation_id": self.conversation.pk, "body_text": "hi"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_participant_sends_a_message(self):
        response = self.post(
            self.alice, {"conversation_id": self.conversation.pk, "body_text": "Thanks!"}
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["body_text"], "Thanks!")
        self.assertEqual(body["conversation_id"], self.conversation.pk)
        self.assertEqual(body["sender_id"], self.alice.pk)
        self.assertFalse(body["read_status"])
        self.assertEqual(Message.objects.get().sender, self.alice)

    def test_sender_comes_from_the_token_not_the_body(self):
        response = self.post(
            self.alice,
            {
                "conversation_id": self.conversation.pk,
                "body_text": "hi",
                "sender_id": self.bob.pk,
                "sender": self.bob.pk,
                "read_status": True,
            },
        )

        self.assertEqual(response.status_code, 201)
        message = Message.objects.get()
        self.assertEqual(message.sender, self.alice)
        self.assertFalse(message.read_status)

    def test_outsider_gets_403_and_nothing_is_stored(self):
        response = self.post(
            self.carol, {"conversation_id": self.conversation.pk, "body_text": "let me in"}
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Message.objects.count(), 0)

    def test_unknown_conversation_is_404(self):
        response = self.post(self.alice, {"conversation_id": 9999, "body_text": "hi"})

        self.assertEqual(response.status_code, 404)

    def test_blank_and_whitespace_only_bodies_are_400(self):
        for body in ("", "   ", "\n\t"):
            with self.subTest(body=body):
                response = self.post(
                    self.alice, {"conversation_id": self.conversation.pk, "body_text": body}
                )
                self.assertEqual(response.status_code, 400)

    def test_2000_characters_is_accepted_and_2001_is_rejected(self):
        ok = self.post(
            self.alice, {"conversation_id": self.conversation.pk, "body_text": "x" * 2000}
        )
        too_long = self.post(
            self.alice, {"conversation_id": self.conversation.pk, "body_text": "x" * 2001}
        )

        self.assertEqual(ok.status_code, 201)
        self.assertEqual(too_long.status_code, 400)
        self.assertEqual(Message.objects.count(), 1)

    def test_limit_counts_characters_not_bytes(self):
        response = self.post(
            self.alice, {"conversation_id": self.conversation.pk, "body_text": "é" * 2000}
        )

        self.assertEqual(response.status_code, 201)

    def test_intentional_whitespace_is_preserved(self):
        self.post(self.alice, {"conversation_id": self.conversation.pk, "body_text": "  hi  "})

        self.assertEqual(Message.objects.get().body_text, "  hi  ")

    def test_markup_is_stored_and_returned_as_plain_text(self):
        text = "<script>alert(1)</script> Tom & Jerry"

        response = self.post(
            self.alice, {"conversation_id": self.conversation.pk, "body_text": text}
        )

        self.assertEqual(response.json()["body_text"], text)
        self.assertEqual(Message.objects.get().body_text, text)

    def test_missing_or_invalid_fields_are_400(self):
        for payload in (
            {},
            {"body_text": "hi"},
            {"conversation_id": self.conversation.pk},
            {"conversation_id": "abc", "body_text": "hi"},
            {"conversation_id": 0, "body_text": "hi"},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.post(self.alice, payload).status_code, 400)

    def test_messages_endpoint_is_post_only(self):
        self.assertEqual(client_for(self.alice).get("/api/chat/messages/").status_code, 405)
        self.assertEqual(client_for(self.alice).delete("/api/chat/messages/").status_code, 405)

    def test_a_sent_message_is_picked_up_by_the_other_users_poll(self):
        first = self.send(self.alice, "earlier")
        sent = self.post(self.alice, {"conversation_id": self.conversation.pk, "body_text": "new"})

        polled = client_for(self.bob).get(self.messages_url() + f"?after={first.pk}").json()

        self.assertEqual([m["id"] for m in polled], [sent.json()["id"]])


class MarkReadTests(ChatApiTestCase):
    def url(self, conversation=None):
        return f"/api/chat/conversations/{(conversation or self.conversation).pk}/read/"

    def test_requires_authentication(self):
        self.assertEqual(APIClient().post(self.url()).status_code, 401)

    def test_marks_only_the_other_persons_messages_read(self):
        self.send(self.alice, "mine")
        self.send(self.bob, "theirs 1")
        self.send(self.bob, "theirs 2")

        response = client_for(self.alice).post(self.url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"conversation_id": self.conversation.pk, "updated_count": 2}
        )
        self.assertFalse(Message.objects.get(body_text="mine").read_status)
        self.assertTrue(Message.objects.get(body_text="theirs 1").read_status)

    def test_repeat_call_updates_nothing(self):
        self.send(self.bob, "theirs")
        client = client_for(self.alice)
        client.post(self.url())

        self.assertEqual(client.post(self.url()).json()["updated_count"], 0)

    def test_clears_the_unread_count(self):
        self.send(self.bob, "theirs")
        client = client_for(self.alice)
        client.post(self.url())

        self.assertEqual(client.get("/api/chat/conversations/").json()[0]["unread_count"], 0)

    def test_outsider_gets_403_and_changes_nothing(self):
        self.send(self.bob, "theirs")

        response = client_for(self.carol).post(self.url())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Message.objects.get().read_status)

    def test_unknown_conversation_is_404(self):
        self.assertEqual(
            client_for(self.alice).post("/api/chat/conversations/9999/read/").status_code, 404
        )

    def test_get_is_not_allowed(self):
        self.assertEqual(client_for(self.alice).get(self.url()).status_code, 405)


class OldOpenRoutesAreGoneTests(ChatApiTestCase):
    def test_conversations_cannot_be_created_edited_or_deleted_over_the_api(self):
        client = client_for(self.alice)
        pk = self.conversation.pk

        created = client.post("/api/chat/conversations/", {}, format="json")
        self.assertEqual(created.status_code, 405)
        self.assertEqual(client.get(f"/api/chat/conversations/{pk}/").status_code, 404)
        self.assertEqual(client.delete(f"/api/chat/conversations/{pk}/").status_code, 404)
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(ConversationParticipant.objects.count(), 2)

    def test_messages_cannot_be_edited_or_deleted_by_id(self):
        message = self.send(self.alice, "mine")
        client = client_for(self.alice)

        url = f"/api/chat/messages/{message.pk}/"
        self.assertEqual(client.patch(url, {}, format="json").status_code, 404)
        self.assertEqual(client.delete(url).status_code, 404)
        self.assertEqual(Message.objects.count(), 1)


class BlockedConversationTests(ChatApiTestCase):
    """A block (either direction) hides the conversation and refuses sends; nothing is deleted."""

    def block(self, blocker, blocked):
        return Block.objects.create(blocker=blocker, blocked=blocked)

    def test_blocker_no_longer_sees_the_conversation(self):
        self.block(self.alice, self.bob)

        self.assertEqual(client_for(self.alice).get("/api/chat/conversations/").json(), [])

    def test_the_blocked_person_no_longer_sees_it_either(self):
        self.block(self.alice, self.bob)

        self.assertEqual(client_for(self.bob).get("/api/chat/conversations/").json(), [])

    def test_history_is_refused_in_both_directions(self):
        self.send(self.alice, "hello")
        self.block(self.bob, self.alice)

        self.assertEqual(client_for(self.alice).get(self.messages_url()).status_code, 403)
        self.assertEqual(client_for(self.bob).get(self.messages_url()).status_code, 403)

    def test_sending_and_marking_read_are_refused(self):
        self.send(self.bob, "hello")
        self.block(self.alice, self.bob)

        sent = client_for(self.alice).post(
            "/api/chat/messages/",
            {"conversation_id": self.conversation.pk, "body_text": "still there?"},
            format="json",
        )
        read = client_for(self.alice).post(f"/api/chat/conversations/{self.conversation.pk}/read/")

        self.assertEqual(sent.status_code, 403)
        self.assertEqual(read.status_code, 403)
        self.assertEqual(Message.objects.count(), 1)
        self.assertFalse(Message.objects.get().read_status)

    def test_a_block_is_soft_and_unblocking_restores_the_conversation(self):
        message = self.send(self.alice, "keep me")
        block = self.block(self.alice, self.bob)

        self.assertTrue(Message.objects.filter(pk=message.pk).exists())  # history is kept

        block.delete()

        self.assertEqual(client_for(self.alice).get(self.messages_url()).status_code, 200)
        self.assertEqual(len(client_for(self.alice).get("/api/chat/conversations/").json()), 1)

    def test_a_block_elsewhere_does_not_hide_other_conversations(self):
        other_request = ConnectionRequest.objects.create(
            sender=self.alice, recipient=self.carol, status=ConnectionRequest.Status.ACCEPTED
        )
        with_carol = create_conversation_from_request(other_request)
        self.block(self.alice, self.bob)

        ids = [row["id"] for row in client_for(self.alice).get("/api/chat/conversations/").json()]

        self.assertEqual(ids, [with_carol.pk])


class SendThrottleTests(ChatApiTestCase):
    def setUp(self):
        cache.clear()  # throttle history is process-wide; isolate each test
        self.addCleanup(cache.clear)

    def post(self, user, text="hi"):
        return client_for(user).post(
            "/api/chat/messages/",
            {"conversation_id": self.conversation.pk, "body_text": text},
            format="json",
        )

    def throttled_to(self, rate):
        return mock.patch.object(MessageSendThrottle, "THROTTLE_RATES", {"message_send": rate})

    def test_default_allows_a_normal_burst(self):
        statuses = {self.post(self.alice, f"m{i}").status_code for i in range(10)}

        self.assertEqual(statuses, {201})

    def test_sending_past_the_limit_returns_429_and_stores_nothing_more(self):
        with self.throttled_to("3/min"):
            statuses = [self.post(self.alice, f"m{i}").status_code for i in range(5)]

        self.assertEqual(statuses, [201, 201, 201, 429, 429])
        self.assertEqual(Message.objects.count(), 3)

    def test_the_limit_is_per_user_not_shared(self):
        with self.throttled_to("2/min"):
            alice = [self.post(self.alice).status_code for _ in range(3)]
            bob = [self.post(self.bob).status_code for _ in range(2)]

        self.assertEqual(alice, [201, 201, 429])
        self.assertEqual(bob, [201, 201])

    def test_reading_and_polling_are_not_throttled(self):
        with self.throttled_to("1/min"):
            self.post(self.alice)
            statuses = {
                client_for(self.bob).get(self.messages_url()).status_code for _ in range(5)
            } | {client_for(self.bob).get("/api/chat/conversations/").status_code for _ in range(5)}

        self.assertEqual(statuses, {200})

    def test_anonymous_calls_still_get_401_not_429(self):
        with self.throttled_to("1/min"):
            statuses = {
                APIClient()
                .post(
                    "/api/chat/messages/",
                    {"conversation_id": self.conversation.pk, "body_text": "x"},
                    format="json",
                )
                .status_code
                for _ in range(3)
            }

        self.assertEqual(statuses, {401})
