"""One test that walks the demo from a stranger's point of view, over HTTP only.

Signup -> verify -> profile -> directory -> connect -> accept -> chat -> referral -> answer.
The other tests in this repo check one rule at a time, so a break *between*
steps (for example a verified account that the directory cannot see) shows up
here first. Nothing is created through the ORM: every account, request and
message comes from an API call, the way the app makes them.
"""

import re

from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

REFERRAL_FIELDS = {
    "id", "sender", "recipient", "company", "role_title", "job_url",
    "resume_url", "message_text", "status", "created_at", "resolved_at",
}


class Member:
    """A person using the app: their own client, and the token they got at login."""

    def __init__(self, email):
        self.email = email
        self.client = APIClient()
        self.user_id = None

    def sign_in(self):
        """Signup, read the emailed code, verify. Returns the verify response."""
        signup = self.client.post(
            "/api/accounts/auth/signup/", {"email": self.email}, format="json"
        )
        assert signup.status_code == 201, signup.content
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        assert mail.outbox[-1].to == [self.email]
        verified = self.client.post(
            "/api/accounts/auth/verify/", {"email": self.email, "code": code}, format="json"
        )
        assert verified.status_code == 200, verified.content
        self.user_id = verified.json()["user_id"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {verified.json()['access']}")
        return verified


class DemoJourneyTests(APITestCase):
    def setUp(self):
        # Throttle history is process-wide; start each test with a full budget. The budget is
        # small: code requests are limited to 5 per 15 minutes per IP and this journey makes 3
        # signups from one client, so a fourth member or a retry here would hit a 429, which
        # shows up as a bare assertion inside Member.sign_in.
        cache.clear()
        self.alice = Member("alice@ncsu.edu")  # a student who wants a referral
        self.bob = Member("bob@ncsu.edu")  # works at Acme
        self.carol = Member("carol@ncsu.edu")  # signs up, but never connects with Alice

    def test_signup_to_referral(self):
        # 1. Everyone signs up and verifies with an emailed code.
        for member in (self.alice, self.bob, self.carol):
            member.sign_in()
        self.assertEqual(len(mail.outbox), 3)

        # 2. Profiles. Bob works at Acme; the company is created from its name.
        profile = self.bob.client.patch(
            "/api/accounts/me/",
            {
                "first_name": "Bob", "last_name": "Builder", "major": "Computer Science",
                "grad_year": 2024, "current_role": "Software Engineer",
                "current_company_name": "Acme", "open_to_connect": True,
            },
            format="json",
        )
        self.assertEqual(profile.status_code, 200, profile.content)
        self.assertEqual(profile.json()["current_company"]["name"], "Acme")
        self.assertEqual(profile.json()["account_status"], "active")
        acme_id = profile.json()["current_company"]["id"]
        self.alice.client.patch(
            "/api/accounts/me/",
            {
                "first_name": "Alice", "last_name": "Student",
                "major": "Computer Science", "grad_year": 2027,
            },
            format="json",
        )

        # 3. Alice finds Bob in the directory by company, and cannot see herself first.
        found = self.alice.client.get(f"/api/accounts/users/?company_id={acme_id}")
        self.assertEqual(found.status_code, 200)
        people = found.json()["results"]
        self.assertEqual([p["user_id"] for p in people], [self.bob.user_id])
        self.assertEqual(people[0]["current_company"]["name"], "Acme")

        # 4. Alice asks to connect. Bob sees it in his inbox, Alice sees it as sent.
        sent = self.alice.client.post(
            "/api/connections/",
            {"recipient_id": self.bob.user_id, "message_text": "Hi Bob, could we chat about Acme?"},
            format="json",
        )
        self.assertEqual(sent.status_code, 201, sent.content)
        request_id = sent.json()["id"]
        self.assertEqual(sent.json()["status"], "pending")

        inbox = self.bob.client.get("/api/connections/?type=incoming").json()
        self.assertEqual([row["id"] for row in inbox], [request_id])
        self.assertEqual(inbox[0]["sender"]["id"], self.alice.user_id)
        outbox = self.alice.client.get("/api/connections/?type=outgoing").json()
        self.assertEqual([row["id"] for row in outbox], [request_id])

        # 5. Until Bob answers, nobody can chat and Alice cannot ask for a referral.
        self.assertEqual(self.alice.client.get("/api/chat/conversations/").json(), [])
        early = self._ask_for_referral(self.alice, self.bob, acme_id)
        self.assertEqual(early.status_code, 403, early.content)

        # 6. Bob accepts, and a conversation exists for both of them.
        accepted = self.bob.client.patch(f"/api/connections/{request_id}/accept/")
        self.assertEqual(accepted.status_code, 200, accepted.content)
        conversation_id = accepted.json()["conversation_id"]
        self.assertIsNotNone(conversation_id)
        self.assertEqual(self.bob.client.get("/api/connections/?type=incoming").json(), [])
        for member in (self.alice, self.bob):
            listed = member.client.get("/api/chat/conversations/").json()
            self.assertEqual([c["id"] for c in listed], [conversation_id])

        # 7. Alice sends a message; Bob fetches it, reads it, and answers.
        message = self.alice.client.post(
            "/api/chat/messages/",
            {"conversation_id": conversation_id, "body_text": "Thanks for accepting!"},
            format="json",
        )
        self.assertEqual(message.status_code, 201, message.content)
        self.assertEqual(message.json()["sender_id"], self.alice.user_id)

        thread_url = f"/api/chat/conversations/{conversation_id}/messages/"
        fetched = self.bob.client.get(thread_url).json()
        self.assertEqual([m["body_text"] for m in fetched], ["Thanks for accepting!"])
        self.assertEqual(fetched[0]["sender_id"], self.alice.user_id)
        read = self.bob.client.post(f"/api/chat/conversations/{conversation_id}/read/")
        self.assertEqual(read.status_code, 200, read.content)

        reply = self.bob.client.post(
            "/api/chat/messages/",
            {"conversation_id": conversation_id, "body_text": "Happy to help."},
            format="json",
        )
        self.assertEqual(reply.status_code, 201, reply.content)
        thread = self.alice.client.get(thread_url).json()
        self.assertEqual(
            [(m["sender_id"], m["body_text"]) for m in thread],
            [(self.alice.user_id, "Thanks for accepting!"), (self.bob.user_id, "Happy to help.")],
        )

        # 8. Now a referral ask works. Every field the UI relies on comes back.
        ask = self._ask_for_referral(self.alice, self.bob, acme_id)
        self.assertEqual(ask.status_code, 201, ask.content)
        referral = ask.json()
        self.assertEqual(set(referral), REFERRAL_FIELDS)
        self.assertEqual(referral["status"], "pending")
        self.assertEqual(referral["company"]["name"], "Acme")
        self.assertEqual(referral["role_title"], "Software Engineer Intern")
        self.assertEqual(referral["job_url"], "https://acme.example/jobs/1")
        self.assertEqual(referral["resume_url"], "https://drive.example/resume")
        self.assertEqual(referral["message_text"], "I built a similar system in my capstone.")
        self.assertEqual(referral["sender"]["id"], self.alice.user_id)
        self.assertEqual(referral["recipient"]["id"], self.bob.user_id)

        # 9. It shows up on both sides, and asking twice for the same role is refused.
        mine = self.alice.client.get("/api/connections/referrals/?type=outgoing").json()
        self.assertEqual([r["id"] for r in mine["results"]], [referral["id"]])
        theirs = self.bob.client.get("/api/connections/referrals/?type=incoming").json()
        self.assertEqual([r["id"] for r in theirs["results"]], [referral["id"]])
        for row in mine["results"] + theirs["results"]:
            self.assertEqual(set(row), REFERRAL_FIELDS)
        again = self._ask_for_referral(self.alice, self.bob, acme_id)
        self.assertEqual(again.status_code, 409, again.content)

        # 10. Carol is a verified member but not Alice's connection: no referral, no chat.
        stranger = self._ask_for_referral(self.alice, self.carol, acme_id)
        self.assertEqual(stranger.status_code, 403, stranger.content)
        self.assertEqual(self.carol.client.get(thread_url).status_code, 403)
        spied = self.carol.client.post(
            "/api/chat/messages/",
            {"conversation_id": conversation_id, "body_text": "let me in"},
            format="json",
        )
        self.assertEqual(spied.status_code, 403, spied.content)
        self.assertEqual(self.carol.client.get("/api/chat/conversations/").json(), [])
        carols_referrals = self.carol.client.get("/api/connections/referrals/?type=incoming")
        self.assertEqual(carols_referrals.json()["results"], [])
        # Carol's attempt added nothing to the thread.
        self.assertEqual(len(self.bob.client.get(thread_url).json()), 2)

        # 11. Only Bob can answer the ask: Carol cannot see it, Alice cannot answer her own.
        answer_url = f"/api/connections/referrals/{referral['id']}/accept/"
        self.assertEqual(self.carol.client.patch(answer_url).status_code, 404)
        self.assertEqual(self.alice.client.patch(answer_url).status_code, 403)
        accepted_ask = self.bob.client.patch(answer_url)
        self.assertEqual(accepted_ask.status_code, 200, accepted_ask.content)
        self.assertEqual(set(accepted_ask.json()), REFERRAL_FIELDS)
        self.assertEqual(accepted_ask.json()["status"], "accepted")
        self.assertIsNotNone(accepted_ask.json()["resolved_at"])
        # Alice sees the answer, and a second answer is refused.
        mine = self.alice.client.get("/api/connections/referrals/?type=outgoing").json()
        self.assertEqual([r["status"] for r in mine["results"]], ["accepted"])
        late = self.bob.client.patch(f"/api/connections/referrals/{referral['id']}/decline/")
        self.assertEqual(late.status_code, 409, late.content)

    def test_a_visitor_with_no_token_is_turned_away_from_every_step(self):
        anonymous = APIClient()
        for method, url in (
            ("get", "/api/accounts/me/"),
            ("get", "/api/accounts/users/"),
            ("get", "/api/connections/?type=incoming"),
            ("post", "/api/connections/"),
            ("get", "/api/chat/conversations/"),
            ("post", "/api/chat/messages/"),
            ("get", "/api/connections/referrals/?type=incoming"),
            ("post", "/api/connections/referrals/"),
        ):
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(anonymous, method)(url).status_code, 401)

    def _ask_for_referral(self, sender, recipient, company_id):
        return sender.client.post(
            "/api/connections/referrals/",
            {
                "recipient_id": recipient.user_id,
                "company_id": company_id,
                "role_title": "Software Engineer Intern",
                "job_url": "https://acme.example/jobs/1",
                "resume_url": "https://drive.example/resume",
                "message_text": "I built a similar system in my capstone.",
            },
            format="json",
        )
