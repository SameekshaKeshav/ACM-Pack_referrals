"""Accept / decline for referral requests.

Mirrors ``test_actions.py`` for connections. Alice asks Bob; Bob answers.
"""

from rest_framework_simplejwt.tokens import AccessToken

from .models import Block, ReferralRequest
from .referrals import ReferralNotPendingError, _resolve_referral
from .test_referrals import ReferralTestCase


class ReferralActionEndpointTests(ReferralTestCase):
    def _pending(self):
        """A pending ask from Alice to Bob, created through the API."""
        self._as(self.alice)
        response = self.client.post("/api/connections/referrals/", self.payload(), format="json")
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    @staticmethod
    def _accept_url(pk):
        return f"/api/connections/referrals/{pk}/accept/"

    @staticmethod
    def _decline_url(pk):
        return f"/api/connections/referrals/{pk}/decline/"

    # --- the deliverable: the recipient can answer, and the answer sticks ---

    def test_recipient_accepts_and_the_detail_shows_accepted(self):
        pk = self._pending()
        self._as(self.bob)

        response = self.client.patch(self._accept_url(pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "accepted")
        self.assertIsNotNone(response.json()["resolved_at"])
        detail = self.client.get(f"/api/connections/referrals/{pk}/")
        self.assertEqual(detail.json()["status"], "accepted")

    def test_recipient_declines(self):
        pk = self._pending()
        self._as(self.bob)

        response = self.client.patch(self._decline_url(pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "declined")

    def test_the_sender_sees_the_answer(self):
        """Sanjana's card has to update for the person who asked."""
        pk = self._pending()
        self._as(self.bob)
        self.client.patch(self._accept_url(pk))

        self._as(self.alice)
        detail = self.client.get(f"/api/connections/referrals/{pk}/")

        self.assertEqual(detail.json()["status"], "accepted")

    # --- who may answer ---

    def test_the_sender_cannot_answer_their_own_ask(self):
        pk = self._pending()
        self._as(self.alice)

        for url in (self._accept_url(pk), self._decline_url(pk)):
            self.assertEqual(self.client.patch(url).status_code, 403)
        self.assertEqual(
            ReferralRequest.objects.get(pk=pk).status, ReferralRequest.Status.PENDING
        )

    def test_an_outsider_gets_not_found(self):
        """Carol is not party to it, so she must not learn that it exists."""
        pk = self._pending()
        self._as(self.carol)

        for url in (self._accept_url(pk), self._decline_url(pk)):
            self.assertEqual(self.client.patch(url).status_code, 404)

    def test_an_unknown_id_returns_not_found(self):
        self._as(self.bob)
        self.assertEqual(self.client.patch(self._accept_url(999999)).status_code, 404)

    def test_an_outsider_and_an_unknown_id_look_the_same(self):
        """Otherwise the pair of responses is an existence oracle."""
        pk = self._pending()
        self._as(self.carol)

        real = self.client.patch(self._accept_url(pk))
        missing = self.client.patch(self._accept_url(999999))

        self.assertEqual(real.status_code, missing.status_code)
        self.assertEqual(real.json(), missing.json())

    def test_anonymous_is_rejected(self):
        pk = self._pending()
        self.client.credentials()

        self.assertEqual(self.client.patch(self._accept_url(pk)).status_code, 401)

    def test_a_blocked_pair_cannot_answer(self):
        """A block hides the ask from GET, so it must hide it from answering too."""
        pk = self._pending()
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        self._as(self.bob)

        self.assertEqual(self.client.get(f"/api/connections/referrals/{pk}/").status_code, 404)
        self.assertEqual(self.client.patch(self._accept_url(pk)).status_code, 404)

    # --- answering twice ---

    def test_answering_twice_returns_conflict(self):
        pk = self._pending()
        self._as(self.bob)
        self.client.patch(self._accept_url(pk))

        again = self.client.patch(self._accept_url(pk))

        self.assertEqual(again.status_code, 409)
        self.assertIn("already", again.json()["detail"].lower())

    def test_declining_after_accepting_returns_conflict_and_keeps_the_answer(self):
        pk = self._pending()
        self._as(self.bob)
        self.client.patch(self._accept_url(pk))

        response = self.client.patch(self._decline_url(pk))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            ReferralRequest.objects.get(pk=pk).status, ReferralRequest.Status.ACCEPTED
        )

    def test_two_simultaneous_answers_cannot_both_succeed(self):
        """The interleaving the conditional UPDATE exists to stop.

        Both callers read the same pending row before either writes, which is
        what two concurrent requests do. The second write must lose, because
        its UPDATE matches no pending row.
        """
        pk = self._pending()
        first = ReferralRequest.objects.get(pk=pk)
        second = ReferralRequest.objects.get(pk=pk)  # the other request's read
        self.assertEqual(second.status, ReferralRequest.Status.PENDING)

        _resolve_referral(first, ReferralRequest.Status.ACCEPTED)
        with self.assertRaises(ReferralNotPendingError):
            _resolve_referral(second, ReferralRequest.Status.DECLINED)

        self.assertEqual(
            ReferralRequest.objects.get(pk=pk).status, ReferralRequest.Status.ACCEPTED
        )

    # --- method and route hygiene ---

    def test_only_patch_is_allowed(self):
        pk = self._pending()
        self._as(self.bob)

        for url in (self._accept_url(pk), self._decline_url(pk)):
            self.assertEqual(self.client.get(url).status_code, 405)
            self.assertEqual(self.client.post(url).status_code, 405)
            self.assertEqual(self.client.delete(url).status_code, 405)

    def test_a_suspended_recipient_can_still_answer(self):
        """Deliberate: answering an existing ask is not sending a new one.

        ``check_may_ask`` stops a suspended member starting new asks. Declining
        one already sent to them is how they tidy up, so it stays allowed.
        """
        from accounts.models import Profile

        pk = self._pending()
        Profile.objects.filter(user=self.bob).update(
            account_status=Profile.AccountStatus.SUSPENDED
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.bob)}")

        self.assertEqual(self.client.patch(self._decline_url(pk)).status_code, 200)
