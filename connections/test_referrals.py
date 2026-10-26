from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import PastRole, Profile
from chat.models import Conversation
from companies.models import Company

from .models import Block, ConnectionRequest, ReferralRequest

User = get_user_model()

URL = "/api/connections/referrals/"


class ReferralTestCase(TestCase):
    """Alice asks Bob (a connection) for a referral. Carol is not connected to Alice."""

    def setUp(self):
        self.client = APIClient()
        self.acme = Company.objects.create(name="Acme")
        self.globex = Company.objects.create(name="Globex")
        self.initech = Company.objects.create(name="Initech")

        self.alice = self._user("alice")
        self.bob = self._user("bob", company=self.acme)
        self.carol = self._user("carol", company=self.acme)
        PastRole.objects.create(user=self.bob, company=self.globex, role_title="Intern")

        self.connect(self.alice, self.bob)

    def _user(self, username, company=None, status=Profile.AccountStatus.ACTIVE):
        user = User.objects.create_user(username=username, first_name=username.title())
        Profile.objects.create(
            user=user, current_company=company, account_status=status, open_to_connect=True
        )
        return user

    def _as(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    @staticmethod
    def connect(one, other, status=ConnectionRequest.Status.ACCEPTED):
        return ConnectionRequest.objects.create(
            sender=one, recipient=other, message_text="hi", status=status
        )

    def payload(self, **overrides):
        body = {
            "recipient_id": self.bob.pk,
            "company_id": self.acme.pk,
            "role_title": "Software Engineer Intern",
            "job_url": "https://acme.example/jobs/1",
            "resume_url": "https://drive.example/resume",
            "message_text": "I built a similar system in my capstone.",
        }
        body.update(overrides)
        return body

    def ask(self, user=None, **overrides):
        self._as(user or self.alice)
        return self.client.post(URL, self.payload(**overrides), format="json")

    def make_referral(self, sender=None, recipient=None, **fields):
        defaults = {"role_title": "SWE", "message_text": "please", "company": self.acme}
        defaults.update(fields)
        return ReferralRequest.objects.create(
            sender=sender or self.alice, recipient=recipient or self.bob, **defaults
        )


class CreateReferralTests(ReferralTestCase):
    def test_a_valid_ask_returns_every_field(self):
        response = self.ask()

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["sender"]["id"], self.alice.pk)
        self.assertEqual(body["recipient"]["id"], self.bob.pk)
        self.assertEqual(body["company"], {"id": self.acme.pk, "name": "Acme"})
        self.assertEqual(body["role_title"], "Software Engineer Intern")
        self.assertEqual(body["job_url"], "https://acme.example/jobs/1")
        self.assertEqual(body["resume_url"], "https://drive.example/resume")
        self.assertEqual(body["message_text"], "I built a similar system in my capstone.")
        self.assertEqual(body["status"], "pending")
        self.assertIsNotNone(body["created_at"])
        self.assertIsNone(body["resolved_at"])
        self.assertTrue(ReferralRequest.objects.filter(pk=body["id"]).exists())

    def test_only_role_title_and_message_are_required(self):
        response = self.ask(company_id=None, job_url="", resume_url="")

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["company"])

    def test_company_and_links_can_be_left_out_entirely(self):
        self._as(self.alice)
        response = self.client.post(
            URL,
            {"recipient_id": self.bob.pk, "role_title": "PM", "message_text": "hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["job_url"], "")

    def test_sender_and_status_come_from_the_token_not_the_body(self):
        response = self.ask(sender_id=self.carol.pk, sender=self.carol.pk, status="accepted")

        self.assertEqual(response.status_code, 201)
        referral = ReferralRequest.objects.get(pk=response.json()["id"])
        self.assertEqual(referral.sender, self.alice)
        self.assertEqual(referral.status, ReferralRequest.Status.PENDING)

    def test_a_referral_ask_does_not_create_a_conversation_or_connection(self):
        conversations = Conversation.objects.count()
        connections = ConnectionRequest.objects.count()

        self.ask()

        self.assertEqual(Conversation.objects.count(), conversations)
        self.assertEqual(ConnectionRequest.objects.count(), connections)

    def test_the_connection_can_have_been_sent_by_either_person(self):
        ConnectionRequest.objects.all().delete()
        self.connect(self.bob, self.alice)

        self.assertEqual(self.ask().status_code, 201)

    def test_role_title_is_trimmed(self):
        response = self.ask(role_title="  Data Analyst  ")

        self.assertEqual(response.json()["role_title"], "Data Analyst")

    def test_text_is_stored_as_typed_not_html_escaped(self):
        response = self.ask(message_text="<b>Tom & Jerry</b>", role_title="R&D <Intern>")

        self.assertEqual(response.json()["message_text"], "<b>Tom & Jerry</b>")
        self.assertEqual(response.json()["role_title"], "R&D <Intern>")

    def test_anonymous_request_is_rejected(self):
        response = self.client.post(URL, self.payload(), format="json")

        self.assertEqual(response.status_code, 401)


class WhoMayAskTests(ReferralTestCase):
    def test_a_non_connection_gets_403(self):
        response = self.ask(recipient_id=self.carol.pk)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ReferralRequest.objects.exists())

    def test_a_pending_connection_is_not_enough(self):
        ConnectionRequest.objects.all().delete()
        self.connect(self.alice, self.bob, ConnectionRequest.Status.PENDING)

        self.assertEqual(self.ask().status_code, 403)

    def test_a_declined_connection_is_not_enough(self):
        ConnectionRequest.objects.all().delete()
        self.connect(self.alice, self.bob, ConnectionRequest.Status.DECLINED)

        self.assertEqual(self.ask().status_code, 403)

    def test_someone_elses_connection_does_not_count(self):
        self.connect(self.bob, self.carol)

        self.assertEqual(self.ask(recipient_id=self.carol.pk).status_code, 403)

    def test_a_block_in_either_direction_gets_403(self):
        for blocker, blocked in ((self.alice, self.bob), (self.bob, self.alice)):
            with self.subTest(blocker=blocker.username):
                Block.objects.all().delete()
                Block.objects.create(blocker=blocker, blocked=blocked)

                self.assertEqual(self.ask().status_code, 403)

    def test_a_suspended_or_unverified_recipient_gets_403(self):
        for status in (Profile.AccountStatus.SUSPENDED, Profile.AccountStatus.UNVERIFIED):
            with self.subTest(status=status):
                Profile.objects.filter(user=self.bob).update(account_status=status)

                self.assertEqual(self.ask().status_code, 403)

    def test_a_suspended_or_unverified_sender_gets_403_and_nothing_is_created(self):
        # A suspended member may still hold a valid token and an accepted connection.
        for status in (Profile.AccountStatus.SUSPENDED, Profile.AccountStatus.UNVERIFIED):
            with self.subTest(status=status):
                Profile.objects.filter(user=self.alice).update(account_status=status)

                response = self.ask()

                self.assertEqual(response.status_code, 403)
                self.assertEqual(ReferralRequest.objects.count(), 0)

    def test_a_sender_without_a_profile_gets_403(self):
        Profile.objects.filter(user=self.alice).delete()

        self.assertEqual(self.ask().status_code, 403)

    def test_the_sender_check_comes_before_the_body_is_validated(self):
        Profile.objects.filter(user=self.alice).update(
            account_status=Profile.AccountStatus.SUSPENDED
        )

        self.assertEqual(self.ask(role_title="", job_url="javascript:x").status_code, 403)

    def test_a_reactivated_sender_can_ask_again(self):
        Profile.objects.filter(user=self.alice).update(
            account_status=Profile.AccountStatus.SUSPENDED
        )
        self.assertEqual(self.ask().status_code, 403)
        Profile.objects.filter(user=self.alice).update(
            account_status=Profile.AccountStatus.ACTIVE
        )

        self.assertEqual(self.ask().status_code, 201)

    def test_every_refusal_has_the_same_message(self):
        not_connected = self.ask(recipient_id=self.carol.pk).json()["detail"]
        Block.objects.create(blocker=self.bob, blocked=self.alice)
        blocked = self.ask().json()["detail"]

        self.assertEqual(not_connected, blocked)

    def test_authorization_is_checked_before_the_body(self):
        response = self.ask(recipient_id=self.carol.pk, role_title="", job_url="javascript:x")

        self.assertEqual(response.status_code, 403)

    def test_asking_yourself_is_a_400(self):
        self.assertEqual(self.ask(recipient_id=self.alice.pk).status_code, 400)

    def test_unknown_recipient_is_a_404(self):
        self.assertEqual(self.ask(recipient_id=999999).status_code, 404)

    def test_missing_or_malformed_recipient_is_a_400(self):
        self._as(self.alice)
        for body in ({}, {"recipient_id": None}, {"recipient_id": "abc"}, {"recipient_id": 0},
                     {"recipient_id": True}):
            with self.subTest(body=body):
                response = self.client.post(URL, {**body, "role_title": "x", "message_text": "y"},
                                            format="json")
                self.assertEqual(response.status_code, 400)

    def test_a_non_object_body_is_a_400(self):
        self._as(self.alice)

        response = self.client.post(URL, [1, 2], format="json")

        self.assertEqual(response.status_code, 400)


class ValidationTests(ReferralTestCase):
    def test_missing_or_blank_role_title_is_a_400(self):
        for value in ("", "   ", None):
            with self.subTest(role_title=value):
                self.assertEqual(self.ask(role_title=value).status_code, 400)

        self._as(self.alice)
        body = self.payload()
        del body["role_title"]
        self.assertEqual(self.client.post(URL, body, format="json").status_code, 400)

    def test_role_title_over_255_is_a_400(self):
        self.assertEqual(self.ask(role_title="x" * 256).status_code, 400)

    def test_non_http_links_are_rejected(self):
        bad = [
            "javascript:alert(1)",
            "JavaScript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "ftp://files.example/resume.pdf",
            "file:///etc/passwd",
            "//acme.example/jobs",
            "not a url",
        ]
        for url in bad:
            for field in ("job_url", "resume_url"):
                with self.subTest(field=field, url=url):
                    response = self.ask(**{field: url})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(field, response.json())

    def test_http_and_https_links_are_accepted(self):
        for url in ("http://acme.example/jobs/1", "https://acme.example/jobs/1?ref=a&b=2"):
            with self.subTest(url=url):
                Block.objects.all().delete()
                ReferralRequest.objects.all().delete()
                self.assertEqual(self.ask(job_url=url).status_code, 201)

    def test_links_over_500_characters_are_a_400(self):
        self.assertEqual(self.ask(job_url="https://a.example/" + "x" * 500).status_code, 400)

    def test_message_text_is_limited_to_500_characters(self):
        self.assertEqual(self.ask(message_text="x" * 501).status_code, 400)
        self.assertEqual(self.ask(message_text="x" * 500).status_code, 201)

    def test_blank_message_text_is_a_400(self):
        for value in ("", "   \n"):
            with self.subTest(message_text=value):
                self.assertEqual(self.ask(message_text=value).status_code, 400)


class CompanyTests(ReferralTestCase):
    def test_the_recipients_current_company_is_allowed(self):
        self.assertEqual(self.ask(company_id=self.acme.pk).status_code, 201)

    def test_a_company_from_the_recipients_past_roles_is_allowed(self):
        response = self.ask(company_id=self.globex.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["company"]["name"], "Globex")

    def test_a_company_not_on_the_recipients_profile_is_a_400(self):
        response = self.ask(company_id=self.initech.pk)

        self.assertEqual(response.status_code, 400)
        self.assertIn("company_id", response.json())

    def test_the_senders_own_company_does_not_count(self):
        PastRole.objects.create(
            user=self.alice, company=self.initech, role_title="Intern",
            start_date=date(2024, 1, 1),
        )

        self.assertEqual(self.ask(company_id=self.initech.pk).status_code, 400)

    def test_an_unknown_company_is_a_400(self):
        self.assertEqual(self.ask(company_id=999999).status_code, 400)


class DuplicateTests(ReferralTestCase):
    def test_a_second_pending_ask_for_the_same_role_is_a_409(self):
        self.assertEqual(self.ask().status_code, 201)

        response = self.ask()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(ReferralRequest.objects.count(), 1)

    def test_role_titles_are_compared_ignoring_case_and_spacing(self):
        self.ask(role_title="Software Engineer Intern")

        self.assertEqual(self.ask(role_title="  software engineer intern ").status_code, 409)

    def test_a_different_role_is_allowed(self):
        self.ask()

        self.assertEqual(self.ask(role_title="Data Scientist").status_code, 201)

    def test_the_same_role_at_another_company_is_allowed(self):
        self.ask(company_id=self.acme.pk)

        self.assertEqual(self.ask(company_id=self.globex.pk).status_code, 201)

    def test_two_asks_without_a_company_for_the_same_role_are_a_409(self):
        self.ask(company_id=None)

        self.assertEqual(self.ask(company_id=None).status_code, 409)

    def test_an_ask_without_a_company_does_not_clash_with_one_that_has_a_company(self):
        self.ask(company_id=self.acme.pk)

        self.assertEqual(self.ask(company_id=None).status_code, 201)

    def test_the_same_role_to_someone_else_is_allowed(self):
        self.connect(self.alice, self.carol)
        self.ask()

        self.assertEqual(self.ask(recipient_id=self.carol.pk).status_code, 201)

    def test_after_a_decline_the_same_ask_can_be_sent_again(self):
        self.ask()
        ReferralRequest.objects.update(status=ReferralRequest.Status.DECLINED)

        self.assertEqual(self.ask().status_code, 201)

    def test_the_database_refuses_a_second_pending_ask_even_if_the_check_is_skipped(self):
        self.make_referral(company=self.acme)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_referral(company=self.acme)

        self.make_referral(company=None)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_referral(company=None)

    def test_the_database_compares_the_role_ignoring_case_like_the_api_does(self):
        # Two simultaneous asks that differ only in capitalisation both pass the
        # read-then-insert check, so the constraint has to catch the second one.
        self.make_referral(role_title="SWE", company=self.acme)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_referral(role_title="swe", company=self.acme)

        self.make_referral(role_title="SWE", company=None)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_referral(role_title="Swe", company=None)

    def test_a_different_role_is_not_caught_by_the_case_insensitive_constraint(self):
        self.make_referral(role_title="SWE", company=self.acme)

        self.make_referral(role_title="SWE Intern", company=self.acme)

        self.assertEqual(ReferralRequest.objects.count(), 2)

    def test_a_lost_race_is_reported_as_409(self):
        from unittest import mock

        from . import referrals

        self.make_referral(role_title="SWE", company=self.acme)
        # Make the up-front check miss the existing row, as if the other request
        # had not committed yet when this one looked.
        with mock.patch.object(
            referrals.ReferralRequest.objects, "filter",
            return_value=ReferralRequest.objects.none(),
        ):
            with self.assertRaises(referrals.DuplicateReferralError):
                referrals.create_referral_request(
                    self.alice, self.bob, company=self.acme, role_title="SWE",
                    job_url="", resume_url="", message_text="again",
                )


class ReadReferralTests(ReferralTestCase):
    def setUp(self):
        super().setUp()
        self.connect(self.carol, self.bob)
        self.first = self.make_referral(role_title="First")
        self.second = self.make_referral(role_title="Second")
        self.from_carol = self.make_referral(sender=self.carol, role_title="Carol's")
        self.to_alice = self.make_referral(
            sender=self.bob, recipient=self.alice, role_title="Reverse", company=None
        )

    def ids(self, response):
        return [row["id"] for row in response.json()["results"]]

    def test_incoming_lists_asks_sent_to_me_newest_first(self):
        self._as(self.bob)

        response = self.client.get(URL, {"type": "incoming"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.ids(response), [self.from_carol.pk, self.second.pk, self.first.pk]
        )

    def test_outgoing_lists_asks_i_sent(self):
        self._as(self.alice)

        response = self.client.get(URL, {"type": "outgoing"})

        self.assertEqual(self.ids(response), [self.second.pk, self.first.pk])

    def test_each_row_has_the_same_fields_as_a_created_ask(self):
        self._as(self.alice)

        row = self.client.get(URL, {"type": "outgoing"}).json()["results"][0]

        self.assertEqual(
            set(row),
            {"id", "sender", "recipient", "company", "role_title", "job_url", "resume_url",
             "message_text", "status", "created_at", "resolved_at"},
        )
        self.assertEqual(row["sender"]["name"], "Alice")
        self.assertEqual(row["recipient"]["company"], "Acme")

    def test_type_is_required_and_validated(self):
        self._as(self.alice)

        for params in ({}, {"type": "all"}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(URL, params).status_code, 400)

    def test_status_can_filter_the_list(self):
        ReferralRequest.objects.filter(pk=self.first.pk).update(
            status=ReferralRequest.Status.ACCEPTED
        )
        self._as(self.bob)

        response = self.client.get(URL, {"type": "incoming", "status": "pending"})

        self.assertEqual(self.ids(response), [self.from_carol.pk, self.second.pk])
        self.assertEqual(
            self.client.get(URL, {"type": "incoming", "status": "nonsense"}).status_code, 400
        )

    def test_a_blocked_users_asks_are_hidden_in_both_directions(self):
        Block.objects.create(blocker=self.bob, blocked=self.alice)

        self._as(self.bob)
        self.assertEqual(self.ids(self.client.get(URL, {"type": "incoming"})),
                         [self.from_carol.pk])
        self._as(self.alice)
        self.assertEqual(self.ids(self.client.get(URL, {"type": "outgoing"})), [])
        self.assertEqual(self.ids(self.client.get(URL, {"type": "incoming"})), [])

    def test_the_list_does_not_query_per_row(self):
        self._as(self.bob)
        self.client.get(URL, {"type": "incoming"})
        for index in range(5):
            extra = self._user(f"extra{index}", company=self.acme)
            self.connect(extra, self.bob)
            self.make_referral(sender=extra, role_title=f"Role {index}")

        # The caller, their blocks, the page's total, and all its rows in one joined query.
        with self.assertNumQueries(4):
            response = self.client.get(URL, {"type": "incoming"})

        self.assertEqual(len(response.json()["results"]), 8)

    def test_the_list_is_paged_with_limit_and_offset(self):
        self._as(self.bob)

        first = self.client.get(URL, {"type": "incoming", "limit": 2}).json()
        second = self.client.get(URL, {"type": "incoming", "limit": 2, "offset": 2}).json()

        self.assertEqual(first["count"], 3)
        self.assertEqual([row["id"] for row in first["results"]],
                         [self.from_carol.pk, self.second.pk])
        self.assertIsNotNone(first["next"])
        self.assertEqual([row["id"] for row in second["results"]], [self.first.pk])
        self.assertIsNone(second["next"])

    def test_a_page_is_capped_at_100_rows(self):
        for index in range(105):
            extra = self._user(f"bulk{index}", company=self.acme)
            self.connect(extra, self.bob)
            self.make_referral(sender=extra, role_title="Bulk")
        self._as(self.bob)

        everything = self.client.get(URL, {"type": "incoming", "limit": 100000}).json()
        default = self.client.get(URL, {"type": "incoming"}).json()

        self.assertEqual(everything["count"], 108)
        self.assertEqual(len(everything["results"]), 100)
        self.assertEqual(len(default["results"]), 20)

    def test_the_detail_is_visible_to_both_people(self):
        for user in (self.alice, self.bob):
            with self.subTest(user=user.username):
                self._as(user)
                response = self.client.get(f"{URL}{self.first.pk}/")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["role_title"], "First")

    def test_an_outsider_gets_404_on_the_detail(self):
        self._as(self.carol)

        self.assertEqual(self.client.get(f"{URL}{self.first.pk}/").status_code, 404)

    def test_a_blocked_pair_gets_404_on_the_detail(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        self._as(self.bob)

        self.assertEqual(self.client.get(f"{URL}{self.first.pk}/").status_code, 404)

    def test_unknown_detail_is_404_and_anonymous_is_401(self):
        self._as(self.alice)
        self.assertEqual(self.client.get(f"{URL}999999/").status_code, 404)

        self.client.credentials()
        self.assertEqual(self.client.get(f"{URL}{self.first.pk}/").status_code, 401)
        self.assertEqual(self.client.get(URL, {"type": "incoming"}).status_code, 401)

    def test_the_detail_route_is_read_only(self):
        self._as(self.bob)

        for method in (self.client.patch, self.client.put, self.client.delete):
            with self.subTest(method=method.__name__):
                self.assertEqual(method(f"{URL}{self.first.pk}/", {}, format="json").status_code,
                                 405)
