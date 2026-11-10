import re
from datetime import timedelta
from unittest import mock

from anymail.exceptions import AnymailAPIError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import AlumniAccessRequest, Profile, VerificationCode
from .throttling import AlumniRequestThrottle
from .views import SEND_FAILED_DETAIL

User = get_user_model()

EMAIL = "testuser@ncsu.edu"


class AuthFlowTests(APITestCase):
    def setUp(self):
        cache.clear()  # throttle history is process-wide; isolate each test
        self.signup_url = reverse("accounts:auth-signup")
        self.verify_url = reverse("accounts:auth-verify")

    def _signup(self, email=EMAIL):
        return self.client.post(self.signup_url, {"email": email}, format="json")

    def _emailed_code(self):
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def test_signup_rejects_non_ncsu_email(self):
        response = self._signup("someone@gatech.edu")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())

    def test_signup_creates_unverified_account_and_emails_a_code(self):
        response = self._signup()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email=EMAIL)
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.profile.account_status, Profile.AccountStatus.UNVERIFIED)
        self.assertEqual(len(mail.outbox), 1)

    def test_signup_stores_only_a_hash_of_the_code(self):
        self._signup()
        stored = User.objects.get(email=EMAIL).verification_codes.first()
        self.assertNotEqual(stored.code_hash, self._emailed_code())
        self.assertTrue(stored.matches(self._emailed_code()))

    def _verify(self, code=None):
        return self.client.post(
            self.verify_url,
            {"email": EMAIL, "code": code or self._emailed_code()},
            format="json",
        )

    def test_signup_for_a_verified_account_returns_conflict(self):
        self._signup()
        self._verify()

        response = self._signup()
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(User.objects.count(), 1)

    def test_signup_for_an_unverified_account_reissues_a_code(self):
        """An unverified address must never be permanently locked out."""
        self._signup()
        first_code = self._emailed_code()

        response = self._signup()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)

        second_code = self._emailed_code()
        self.assertNotEqual(first_code, second_code)

        self.assertEqual(
            self._verify(first_code).status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(self._verify(second_code).status_code, status.HTTP_200_OK)

    def test_an_expired_code_can_be_replaced_by_signing_up_again(self):
        self._signup()
        stored = User.objects.get(email=EMAIL).verification_codes.first()
        stored.expires_at = timezone.now() - timedelta(seconds=1)
        stored.save(update_fields=["expires_at"])

        self._signup()
        self.assertEqual(self._verify().status_code, status.HTTP_200_OK)

    def test_concurrent_signup_losing_the_race_returns_conflict(self):
        """A second request that slips past the existence check must not 500."""
        with mock.patch.object(
            User, "save", side_effect=IntegrityError("duplicate username")
        ):
            response = self._signup()
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_verify_rejects_a_wrong_code(self):
        self._signup()
        wrong = "000000" if self._emailed_code() != "000000" else "111111"
        response = self.client.post(
            self.verify_url, {"email": EMAIL, "code": wrong}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.get(email=EMAIL).is_active)

    def test_verify_rejects_an_expired_code(self):
        self._signup()
        code = self._emailed_code()
        stored = User.objects.get(email=EMAIL).verification_codes.first()
        stored.expires_at = timezone.now() - timedelta(seconds=1)
        stored.save(update_fields=["expires_at"])

        response = self.client.post(
            self.verify_url, {"email": EMAIL, "code": code}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_activates_the_account_and_returns_tokens(self):
        self._signup()
        response = self.client.post(
            self.verify_url,
            {"email": EMAIL, "code": self._emailed_code()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(email=EMAIL)
        self.assertTrue(user.is_active)
        self.assertEqual(user.profile.account_status, Profile.AccountStatus.ACTIVE)

        self.assertEqual(response.data["user_id"], user.id)

        # simplejwt serialises the user_id claim as a string.
        token = AccessToken(response.data["access"])
        self.assertEqual(str(token["user_id"]), str(user.id))
        self.assertEqual(token["exp"] - token["iat"], 24 * 60 * 60)

    def test_code_is_single_use(self):
        self._signup()
        code = self._emailed_code()
        self.client.post(self.verify_url, {"email": EMAIL, "code": code}, format="json")

        response = self.client.post(
            self.verify_url, {"email": EMAIL, "code": code}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_does_not_reveal_whether_an_account_exists(self):
        self._signup()
        known = self.client.post(
            self.verify_url, {"email": EMAIL, "code": "000000"}, format="json"
        )
        unknown = self.client.post(
            self.verify_url,
            {"email": "nobody@ncsu.edu", "code": "000000"},
            format="json",
        )
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.data, unknown.data)

    def test_issuing_a_new_code_invalidates_the_previous_one(self):
        self._signup()
        user = User.objects.get(email=EMAIL)
        first = self._emailed_code()

        VerificationCode.issue(user)
        self.assertEqual(user.verification_codes.count(), 1)

        response = self.client.post(
            self.verify_url, {"email": EMAIL, "code": first}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    def setUp(self):
        cache.clear()  # throttle history is process-wide; isolate each test
        self.signup_url = reverse("accounts:auth-signup")
        self.login_url = reverse("accounts:auth-login")
        self.verify_url = reverse("accounts:auth-verify")

    def _emailed_code(self):
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def _verified_account(self):
        self.client.post(self.signup_url, {"email": EMAIL}, format="json")
        self.client.post(
            self.verify_url,
            {"email": EMAIL, "code": self._emailed_code()},
            format="json",
        )

    def test_login_sends_a_fresh_code_to_a_verified_account(self):
        self._verified_account()
        mail.outbox.clear()

        response = self.client.post(self.login_url, {"email": EMAIL}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        verify = self.client.post(
            self.verify_url,
            {"email": EMAIL, "code": self._emailed_code()},
            format="json",
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)
        self.assertIn("access", verify.data)

    def test_login_does_not_reveal_whether_an_account_exists(self):
        self._verified_account()
        known = self.client.post(self.login_url, {"email": EMAIL}, format="json")
        unknown = self.client.post(
            self.login_url, {"email": "nobody@ncsu.edu"}, format="json"
        )
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.data, unknown.data)

    def test_login_for_an_unknown_account_sends_no_email(self):
        mail.outbox.clear()
        self.client.post(self.login_url, {"email": "nobody@ncsu.edu"}, format="json")
        self.assertEqual(len(mail.outbox), 0)

    def test_login_rejects_a_non_ncsu_address(self):
        response = self.client.post(
            self.login_url, {"email": "someone@gatech.edu"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_invalidates_the_previous_code(self):
        self.client.post(self.signup_url, {"email": EMAIL}, format="json")
        first = self._emailed_code()

        self.client.post(self.login_url, {"email": EMAIL}, format="json")
        stale = self.client.post(
            self.verify_url, {"email": EMAIL, "code": first}, format="json"
        )
        self.assertEqual(stale.status_code, status.HTTP_400_BAD_REQUEST)

    def test_suspended_account_cannot_login_or_verify(self):
        user = User.objects.create_user(username=EMAIL, email=EMAIL, is_active=True)
        Profile.objects.create(
            user=user,
            account_status=Profile.AccountStatus.SUSPENDED,
        )
        verification, code = VerificationCode.issue(user)

        login = self.client.post(self.login_url, {"email": EMAIL}, format="json")
        verify = self.client.post(
            self.verify_url,
            {"email": EMAIL, "code": code},
            format="json",
        )

        self.assertEqual(login.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(verify.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(VerificationCode.objects.filter(pk=verification.pk).exists())


class SendFailureTests(APITestCase):
    """The email provider being down (or out of quota) must not cause a 500,
    and must not let login reveal which addresses are registered."""

    def setUp(self):
        cache.clear()  # throttle history is process-wide; isolate each test
        self.signup_url = reverse("accounts:auth-signup")
        self.login_url = reverse("accounts:auth-login")
        self.verify_url = reverse("accounts:auth-verify")

    def _post(self, url, email=EMAIL):
        return self.client.post(url, {"email": email}, format="json")

    def _failing_send(self):
        return mock.patch(
            "accounts.views.send_mail", side_effect=AnymailAPIError("Brevo unreachable")
        )

    def test_signup_returns_503_and_logs_when_the_send_fails(self):
        with self._failing_send(), self.assertLogs("accounts.views", "ERROR") as logs:
            response = self._post(self.signup_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["detail"], SEND_FAILED_DETAIL)
        self.assertIn("Brevo unreachable", logs.output[0])
        # The account exists but is unverified, so nothing is lost.
        self.assertFalse(User.objects.get(email=EMAIL).is_active)

    def test_signup_can_be_retried_after_a_failed_send(self):
        with self._failing_send(), self.assertLogs("accounts.views", "ERROR"):
            self._post(self.signup_url)

        retry = self._post(self.signup_url)
        self.assertEqual(retry.status_code, status.HTTP_201_CREATED)
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        verify = self.client.post(
            self.verify_url, {"email": EMAIL, "code": code}, format="json"
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)

    def test_signup_reissue_for_an_unverified_account_also_returns_503(self):
        self._post(self.signup_url)  # unverified account, first send works

        with self._failing_send(), self.assertLogs("accounts.views", "ERROR"):
            response = self._post(self.signup_url)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_login_failure_looks_the_same_as_an_unknown_account(self):
        User.objects.create_user(username=EMAIL, email=EMAIL)
        unknown = self._post(self.login_url, "nobody@ncsu.edu")

        with self._failing_send(), self.assertLogs("accounts.views", "ERROR") as logs:
            known = self._post(self.login_url)

        self.assertEqual(known.status_code, status.HTTP_200_OK)
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.data, unknown.data)
        self.assertIn("Brevo unreachable", logs.output[0])


class TokenRefreshTests(APITestCase):
    def setUp(self):
        cache.clear()  # throttle history is process-wide; isolate each test
        self.refresh_url = reverse("accounts:auth-refresh")
        self.signup_url = reverse("accounts:auth-signup")
        self.verify_url = reverse("accounts:auth-verify")
        self.client.post(self.signup_url, {"email": EMAIL}, format="json")
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        self.tokens = self.client.post(
            self.verify_url, {"email": EMAIL, "code": code}, format="json"
        ).data

    def test_a_refresh_token_buys_a_new_access_token(self):
        response = self.client.post(
            self.refresh_url, {"refresh": self.tokens["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

        user = User.objects.get(email=EMAIL)
        token = AccessToken(response.data["access"])
        self.assertEqual(str(token["user_id"]), str(user.id))

    def test_the_new_access_token_actually_works(self):
        fresh = self.client.post(
            self.refresh_url, {"refresh": self.tokens["refresh"]}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {fresh}")
        self.assertEqual(self.client.get("/api/companies/").status_code, 200)

    def test_refresh_requires_no_access_token_of_its_own(self):
        """The caller's access token has expired by definition."""
        self.client.credentials()
        response = self.client.post(
            self.refresh_url, {"refresh": self.tokens["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_garbage_refresh_token_is_rejected(self):
        response = self.client.post(
            self.refresh_url, {"refresh": "not.a.real.token"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.signup_url = reverse("accounts:auth-signup")
        self.login_url = reverse("accounts:auth-login")
        self.verify_url = reverse("accounts:auth-verify")

    def test_a_sixth_code_request_in_the_window_is_rejected(self):
        for i in range(5):
            response = self.client.post(
                self.signup_url, {"email": f"user{i}@ncsu.edu"}, format="json"
            )
            self.assertNotEqual(
                response.status_code, 429, f"request {i + 1} was throttled"
            )

        sixth = self.client.post(
            self.signup_url, {"email": "user5@ncsu.edu"}, format="json"
        )
        self.assertEqual(sixth.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_signup_and_login_share_one_budget(self):
        """Both send mail, so they are throttled together rather than 5 each."""
        for i in range(5):
            self.client.post(
                self.signup_url, {"email": f"u{i}@ncsu.edu"}, format="json"
            )

        response = self.client.post(self.login_url, {"email": EMAIL}, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_verify_has_its_own_budget(self):
        """Being throttled on signup must not lock a user out of verifying."""
        self.client.post(self.signup_url, {"email": EMAIL}, format="json")
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        for i in range(1, 5):
            self.client.post(
                self.signup_url, {"email": f"x{i}@ncsu.edu"}, format="json"
            )

        response = self.client.post(
            self.verify_url, {"email": EMAIL, "code": code}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


@override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, "NUM_PROXIES": 1})
class ProxyThrottleTests(APITestCase):
    """Behind one proxy, only the last X-Forwarded-For entry identifies the
    client: the proxy appends it, and the client controls everything before it."""

    def setUp(self):
        cache.clear()
        self.signup_url = reverse("accounts:auth-signup")

    def signup(self, i, forwarded_for):
        return self.client.post(
            self.signup_url,
            {"email": f"user{i}@ncsu.edu"},
            format="json",
            HTTP_X_FORWARDED_FOR=forwarded_for,
        )

    def test_a_spoofed_forwarded_for_does_not_reset_the_budget(self):
        for i in range(5):
            self.signup(i, f"10.0.0.{i}, 203.0.113.7")

        response = self.signup(5, "10.0.0.99, 203.0.113.7")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_each_real_client_gets_its_own_budget(self):
        for i in range(5):
            self.signup(i, "203.0.113.7")

        response = self.signup(5, "198.51.100.1")
        self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class VerifyAttemptCapTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.signup_url = reverse("accounts:auth-signup")
        self.verify_url = reverse("accounts:auth-verify")
        self.client.post(self.signup_url, {"email": EMAIL}, format="json")
        self.code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        self.user = User.objects.get(email=EMAIL)

    def _guess(self, code="000000"):
        return self.client.post(
            self.verify_url, {"email": EMAIL, "code": code}, format="json"
        )

    def test_failed_attempts_are_counted(self):
        self._guess()
        self.assertEqual(self.user.verification_codes.first().attempts, 1)
        self._guess()
        self.assertEqual(self.user.verification_codes.first().attempts, 2)

    def test_the_code_is_destroyed_after_the_cap(self):
        for _ in range(settings.VERIFICATION_MAX_ATTEMPTS):
            self._guess()
        self.assertEqual(self.user.verification_codes.count(), 0)

    def test_the_correct_code_no_longer_works_once_the_cap_is_hit(self):
        """This is the point: guessing cannot be continued past the cap."""
        for _ in range(settings.VERIFICATION_MAX_ATTEMPTS):
            self._guess()

        response = self._guess(self.code)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_exhausting_a_code_does_not_lock_the_account_out(self):
        for _ in range(settings.VERIFICATION_MAX_ATTEMPTS):
            self._guess()

        self.client.post(self.signup_url, {"email": EMAIL}, format="json")
        fresh = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        response = self._guess(fresh)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_successful_verify_does_not_count_as_a_failure(self):
        self._guess()
        response = self._guess(self.code)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class UserDirectoryTests(APITestCase):
    """The tracker's deliverable: combinable filters over 5+ members."""

    @classmethod
    def setUpTestData(cls):
        from companies.models import Company
        from accounts.models import PastRole

        cls.google = Company.objects.create(name="Google")
        cls.ibm = Company.objects.create(name="IBM")

        def member(username, major, grad_year, current=None, past=None, status_="active"):
            user = User.objects.create_user(
                username=username, first_name=username.title(), last_name="S"
            )
            Profile.objects.create(
                user=user, major=major, grad_year=grad_year,
                current_company=current, account_status=status_,
            )
            if past:
                PastRole.objects.create(user=user, company=past, role_title="Intern")
            return user

        cls.alice = member("alice", "Computer Science", 2027, current=cls.google)
        cls.bob = member("bob", "Computer Science", 2027, past=cls.google)
        cls.carol = member("carol", "Computer Science", 2026, current=cls.google)
        cls.dave = member("dave", "Statistics", 2027, current=cls.google)
        cls.erin = member("erin", "Computer Science", 2027, current=cls.ibm)
        member("frank", "Computer Science", 2027, current=cls.google, status_="unverified")
        member("gina", "Computer Science", 2027, current=cls.google, status_="suspended")
        cls.viewer = member("viewer", "", None)

    def setUp(self):
        cache.clear()
        self.url = reverse("accounts:user-directory")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.viewer)}"
        )

    def names(self, query=""):
        response = self.client.get(f"{self.url}{query}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return sorted(row["name"] for row in response.data["results"])

    def test_all_three_filters_combined(self):
        """CS + 2027 + Google: alice is current there, bob held a role there.

        Everyone else is excluded for exactly one reason: carol's year, dave's
        major, erin's company, frank unverified, gina suspended.
        """
        got = self.names(
            f"?major=Computer Science&grad_year=2027&company_id={self.google.pk}"
        )
        self.assertEqual(got, ["Alice S", "Bob S"])

    def test_company_filter_matches_current_or_past(self):
        got = self.names(f"?company_id={self.google.pk}")
        self.assertEqual(got, ["Alice S", "Bob S", "Carol S", "Dave S"])

    def test_major_filter_is_a_substring_match(self):
        self.assertEqual(
            self.names("?major=computer"),
            ["Alice S", "Bob S", "Carol S", "Erin S"],
        )

    def test_repeated_major_means_any_of_them(self):
        self.assertEqual(
            self.names("?major=Statistics&major=Computer Science"),
            ["Alice S", "Bob S", "Carol S", "Dave S", "Erin S"],
        )

    def test_repeated_major_still_combines_with_the_other_filters(self):
        got = self.names("?major=Statistics&major=Computer Science&grad_year=2026")
        self.assertEqual(got, ["Carol S"])

    def test_blank_majors_are_ignored(self):
        self.assertEqual(self.names("?major=&major=%20"), self.names())

    def test_too_many_majors_is_a_400(self):
        query = "?" + "&".join(f"major=m{i}" for i in range(11))
        self.assertEqual(self.client.get(f"{self.url}{query}").status_code,
                         status.HTTP_400_BAD_REQUEST)

    def test_grad_year_filter(self):
        self.assertEqual(self.names("?grad_year=2026"), ["Carol S"])

    def test_unverified_and_suspended_members_are_hidden(self):
        everyone = self.names()
        self.assertNotIn("Frank S", everyone)
        self.assertNotIn("Gina S", everyone)

    def test_someone_affiliated_twice_appears_once(self):
        from accounts.models import PastRole

        PastRole.objects.create(user=self.alice, company=self.google, role_title="Intern")
        got = self.names(f"?company_id={self.google.pk}")
        self.assertEqual(got.count("Alice S"), 1)

    def test_pagination_limit_and_offset(self):
        first = self.client.get(f"{self.url}?limit=2")
        self.assertEqual(len(first.data["results"]), 2)
        self.assertEqual(first.data["count"], 6)
        self.assertIsNotNone(first.data["next"])

        second = self.client.get(f"{self.url}?limit=2&offset=2")
        self.assertEqual(len(second.data["results"]), 2)
        self.assertNotEqual(
            [r["user_id"] for r in first.data["results"]],
            [r["user_id"] for r in second.data["results"]],
        )

    def test_limit_is_capped(self):
        response = self.client.get(f"{self.url}?limit=100000")
        self.assertLessEqual(len(response.data["results"]), 100)

    def test_non_numeric_filters_are_rejected(self):
        for query in ("?grad_year=abc", "?company_id=xyz", "?grad_year=-1"):
            with self.subTest(query=query):
                response = self.client.get(f"{self.url}{query}")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_directory_requires_a_token(self):
        anon = self.client_class()
        self.assertEqual(anon.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_entries_do_not_expose_contact_details(self):
        response = self.client.get(self.url)
        row = response.data["results"][0]
        self.assertNotIn("bio", row)
        self.assertNotIn("email", row)
        self.assertIn("open_to_connect", row)


class MeEndpointTests(APITestCase):
    def setUp(self):
        cache.clear()
        from companies.models import Company
        from accounts.models import PastRole

        self.url = reverse("accounts:me")
        self.user = User.objects.create_user(
            username=EMAIL, email=EMAIL, first_name="Jane", last_name="Doe"
        )
        self.profile = Profile.objects.create(
            user=self.user, major="Computer Science", grad_year=2028,
            bio="Sophomore.", account_status=Profile.AccountStatus.ACTIVE,
        )
        self.google = Company.objects.create(name="Google")
        PastRole.objects.create(
            user=self.user, company=self.google, role_title="SWE Intern",
            start_date="2025-05-01", end_date="2025-08-01",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}"
        )

    def test_get_returns_the_callers_own_profile_with_roles(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user_id"], self.user.pk)
        self.assertEqual(response.data["name"], "Jane Doe")
        self.assertEqual(len(response.data["past_roles"]), 1)
        self.assertEqual(response.data["past_roles"][0]["company"]["name"], "Google")

    def test_patch_updates_editable_fields(self):
        response = self.client.patch(
            self.url, {"bio": "Junior now.", "major": "Statistics", "grad_year": 2027},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, "Junior now.")
        self.assertEqual(self.profile.major, "Statistics")

    def test_patch_updates_the_name_through_the_user_model(self):
        self.client.patch(self.url, {"first_name": "Janet"}, format="json")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Janet")
        self.assertEqual(self.client.get(self.url).data["name"], "Janet Doe")

    def test_current_employer_is_set_by_name_and_deduped(self):
        from companies.models import Company

        response = self.client.patch(
            self.url, {"current_company_name": "  google inc. "}, format="json"
        )
        self.assertEqual(response.data["current_company"]["id"], self.google.pk)
        self.assertEqual(Company.objects.count(), 1)

    def test_a_blank_employer_name_clears_it(self):
        self.client.patch(self.url, {"current_company_name": "Google"}, format="json")
        response = self.client.patch(self.url, {"current_company_name": ""}, format="json")
        self.assertIsNone(response.data["current_company"])

    def test_read_only_fields_cannot_be_written(self):
        self.client.patch(
            self.url,
            {"email": "attacker@ncsu.edu", "account_status": "suspended"},
            format="json",
        )
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.email, EMAIL)
        self.assertEqual(self.profile.account_status, Profile.AccountStatus.ACTIVE)

    def test_put_is_not_allowed(self):
        response = self.client.put(self.url, {"bio": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_requires_a_token(self):
        anon = self.client_class()
        self.assertEqual(anon.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_an_account_without_a_profile_gets_404(self):
        stray = User.objects.create_user(username="stray")
        client = self.client_class()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(stray)}")
        self.assertEqual(client.get(self.url).status_code, status.HTTP_404_NOT_FOUND)

    def test_the_profiles_route_is_gone(self):
        """It was an uncurated third view of people, listing suspended and
        unverified members with their bio. /users/ and /me/ replace it."""
        victim = User.objects.create_user(username="victim")
        other = Profile.objects.create(user=victim, bio="untouched")

        for path in ("/api/accounts/profiles/", f"/api/accounts/profiles/{other.pk}/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, status.HTTP_404_NOT_FOUND)

        self.assertEqual(
            self.client.patch(
                f"/api/accounts/profiles/{other.pk}/", {"bio": "hacked"}, format="json"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        other.refresh_from_db()
        self.assertEqual(other.bio, "untouched")

    def test_a_suspended_member_is_not_reachable_anywhere(self):
        """The leak Sameeksha found: suspended profiles were listable."""
        hidden = User.objects.create_user(username="hidden", first_name="Hidden")
        Profile.objects.create(
            user=hidden, bio="private", account_status=Profile.AccountStatus.SUSPENDED
        )

        directory = self.client.get(reverse("accounts:user-directory"))
        self.assertNotIn("Hidden", [row["name"] for row in directory.data["results"]])
        self.assertEqual(
            self.client.get(f"/api/accounts/profiles/{hidden.profile.pk}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_grad_year_outside_a_sane_range_is_rejected(self):
        for bad in (1800, 3000):
            with self.subTest(bad=bad):
                response = self.client.patch(self.url, {"grad_year": bad}, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            self.client.patch(self.url, {"grad_year": 2028}, format="json").status_code,
            status.HTTP_200_OK,
        )

    def test_a_suffix_only_employer_name_is_rejected(self):
        response = self.client.patch(
            self.url, {"current_company_name": "Inc."}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


def _rate(value):
    """Raise the alumni throttle so a functional test is not starved by it.

    Patches the throttle class rather than using override_settings: DRF binds
    SimpleRateThrottle.THROTTLE_RATES to the settings dict at import, so
    overriding REST_FRAMEWORK later leaves the old rates in place. (NUM_PROXIES
    is read per request, which is why ProxyThrottleTests can override it.)

    The real 3/15min budget is exercised in AlumniRequestThrottleTests.
    """
    return mock.patch.dict(
        AlumniRequestThrottle.THROTTLE_RATES, {"alumni_request": value}
    )


VALID_REQUEST = {
    "email": "alum@gmail.com",
    "full_name": "Jo Alum",
    "unity_id": "jalum",
    "grad_year": 2019,
    "major": "Computer Science",
    "linkedin_url": "https://www.linkedin.com/in/joalum/",
    "note": "Class of 2019, happy to take referral questions.",
}


@_rate("1000/15min")
class AlumniAccessRequestSubmissionTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("accounts:alumni-access-request")

    def submit(self, **overrides):
        payload = {**VALID_REQUEST, **overrides}
        return self.client.post(self.url, payload, format="json")

    def test_a_valid_request_is_stored(self):
        response = self.submit()
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        req = AlumniAccessRequest.objects.get()
        self.assertEqual(req.email, "alum@gmail.com")
        self.assertEqual(req.status, AlumniAccessRequest.Status.PENDING)
        self.assertIsNone(req.reviewed_by)

    def test_the_endpoint_needs_no_token(self):
        self.assertEqual(self.submit().status_code, status.HTTP_202_ACCEPTED)

    def test_email_and_unity_id_are_normalized(self):
        self.submit(email="  ALUM@Gmail.COM ", unity_id="  JAlum ")
        req = AlumniAccessRequest.objects.get()
        self.assertEqual(req.email, "alum@gmail.com")
        self.assertEqual(req.unity_id, "jalum")

    def test_the_response_never_echoes_the_submission_back(self):
        """Write-only: the reply must not become a way to read requests."""
        response = self.submit()
        self.assertEqual(set(response.data), {"detail"})

    def test_a_bad_unity_id_is_a_400(self):
        for bad in ("j.doe", "2jdoe", "jdoe!", "", "a" * 40):
            with self.subTest(unity_id=bad):
                response = self.submit(unity_id=bad)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("unity_id", response.data)

    def test_digits_after_letters_are_accepted(self):
        self.assertEqual(self.submit(unity_id="jdoe2").status_code, status.HTTP_202_ACCEPTED)

    def test_a_missing_required_field_is_a_400(self):
        for field in ("email", "full_name", "unity_id", "grad_year", "major"):
            with self.subTest(field=field):
                payload = {k: v for k, v in VALID_REQUEST.items() if k != field}
                response = self.client.post(self.url, payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

    def test_linkedin_and_note_are_optional(self):
        payload = {k: v for k, v in VALID_REQUEST.items() if k not in ("linkedin_url", "note")}
        self.assertEqual(
            self.client.post(self.url, payload, format="json").status_code,
            status.HTTP_202_ACCEPTED,
        )

    def test_an_over_long_note_is_a_400_not_an_unbounded_write(self):
        """Issue #27 is unbounded TextFields; this endpoint does not add one."""
        response = self.submit(note="x" * 501)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("note", response.data)

    def test_an_implausible_grad_year_is_a_400(self):
        for year in (1800, 2200):
            with self.subTest(year=year):
                self.assertEqual(
                    self.submit(grad_year=year).status_code, status.HTTP_400_BAD_REQUEST
                )

    def test_status_and_reviewer_cannot_be_set_from_the_body(self):
        response = self.submit(status="approved", reviewed_by=1, reviewed_at="2026-01-01T00:00:00Z")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        req = AlumniAccessRequest.objects.get()
        self.assertEqual(req.status, AlumniAccessRequest.Status.PENDING)
        self.assertIsNone(req.reviewed_by)
        self.assertIsNone(req.reviewed_at)


@_rate("1000/15min")
class AlumniRequestDuplicateTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("accounts:alumni-access-request")

    def submit(self, **overrides):
        return self.client.post(self.url, {**VALID_REQUEST, **overrides}, format="json")

    def test_a_second_pending_request_is_not_stored(self):
        self.assertEqual(self.submit().status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(self.submit().status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(AlumniAccessRequest.objects.count(), 1)

    def test_a_duplicate_is_indistinguishable_from_a_first_submission(self):
        """Otherwise the endpoint reports who has already applied."""
        first = self.submit()
        second = self.submit()
        self.assertEqual(first.status_code, second.status_code)
        self.assertEqual(first.data, second.data)

    def test_the_database_refuses_a_second_pending_row(self):
        """The serializer check races; the constraint is what actually holds."""
        AlumniAccessRequest.objects.create(**VALID_REQUEST)
        with self.assertRaises(IntegrityError):
            AlumniAccessRequest.objects.create(**VALID_REQUEST)

    def test_reapplying_after_a_rejection_is_allowed(self):
        AlumniAccessRequest.objects.create(
            **VALID_REQUEST, status=AlumniAccessRequest.Status.REJECTED
        )
        self.assertEqual(self.submit().status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(AlumniAccessRequest.objects.count(), 2)

    def test_a_clashing_unity_id_is_flagged_not_rejected(self):
        self.submit()
        self.submit(email="other@gmail.com")
        other = AlumniAccessRequest.objects.get(email="other@gmail.com")
        self.assertTrue(other.other_requests_with_this_unity_id().exists())
        self.assertEqual(AlumniAccessRequest.objects.count(), 2)


@_rate("1000/15min")
class AlumniRequestHoneypotTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("accounts:alumni-access-request")

    def test_a_filled_honeypot_stores_nothing(self):
        response = self.client.post(
            self.url, {**VALID_REQUEST, "confirm_email": "alum@gmail.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(AlumniAccessRequest.objects.count(), 0)

    def test_a_blank_honeypot_is_fine(self):
        response = self.client.post(
            self.url, {**VALID_REQUEST, "confirm_email": ""}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(AlumniAccessRequest.objects.count(), 1)

    def test_the_honeypot_response_matches_a_real_one(self):
        real = self.client.post(self.url, VALID_REQUEST, format="json")
        cache.clear()
        AlumniAccessRequest.objects.all().delete()
        trapped = self.client.post(
            self.url, {**VALID_REQUEST, "confirm_email": "x@y.com"}, format="json"
        )
        self.assertEqual(real.status_code, trapped.status_code)
        self.assertEqual(real.data, trapped.data)


class AlumniRequestThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("accounts:alumni-access-request")

    def test_a_fourth_request_in_the_window_is_rejected(self):
        for i in range(3):
            response = self.client.post(
                self.url, {**VALID_REQUEST, "email": f"alum{i}@gmail.com"}, format="json"
            )
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        response = self.client.post(
            self.url, {**VALID_REQUEST, "email": "alum9@gmail.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_it_has_its_own_budget_separate_from_code_requests(self):
        for i in range(3):
            self.client.post(
                self.url, {**VALID_REQUEST, "email": f"alum{i}@gmail.com"}, format="json"
            )
        signup = self.client.post(
            reverse("accounts:auth-signup"), {"email": "student@ncsu.edu"}, format="json"
        )
        self.assertNotEqual(signup.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


@override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, "NUM_PROXIES": 1})
class AlumniRequestProxyThrottleTests(APITestCase):
    """The same proxy-aware client identification as the auth throttles.

    Issue #28: with the proxy count unset, a varying X-Forwarded-For bypassed
    throttling entirely. A new public endpoint has to be covered too.
    """

    def setUp(self):
        cache.clear()
        self.url = reverse("accounts:alumni-access-request")

    def submit(self, i, forwarded_for):
        return self.client.post(
            self.url,
            {**VALID_REQUEST, "email": f"alum{i}@gmail.com"},
            format="json",
            HTTP_X_FORWARDED_FOR=forwarded_for,
        )

    def test_a_spoofed_forwarded_for_does_not_reset_the_budget(self):
        for i in range(3):
            self.submit(i, f"9.9.9.{i}, 10.0.0.1")
        response = self.submit(9, "9.9.9.250, 10.0.0.1")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_each_real_client_gets_its_own_budget(self):
        for i in range(3):
            self.submit(i, f"9.9.9.{i}, 10.0.0.1")
        response = self.submit(9, "9.9.9.250, 10.0.0.2")
        self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


@_rate("1000/15min")
class ApprovedAlumniSignupTests(APITestCase):
    """An approved address becomes eligible on every auth endpoint."""

    def setUp(self):
        cache.clear()
        self.signup_url = reverse("accounts:auth-signup")
        self.login_url = reverse("accounts:auth-login")
        self.verify_url = reverse("accounts:auth-verify")

    def approve(self, email="alum@gmail.com"):
        return AlumniAccessRequest.objects.create(
            **{**VALID_REQUEST, "email": email},
            status=AlumniAccessRequest.Status.APPROVED,
        )

    def test_an_unapproved_non_ncsu_address_is_still_rejected(self):
        response = self.client.post(
            self.signup_url, {"email": "stranger@gmail.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_a_pending_request_does_not_grant_access(self):
        AlumniAccessRequest.objects.create(**VALID_REQUEST)
        response = self.client.post(
            self.signup_url, {"email": "alum@gmail.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_rejected_request_does_not_grant_access(self):
        AlumniAccessRequest.objects.create(
            **VALID_REQUEST, status=AlumniAccessRequest.Status.REJECTED
        )
        response = self.client.post(
            self.signup_url, {"email": "alum@gmail.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_an_approved_alum_can_sign_up_and_is_marked_admin_approved(self):
        self.approve()
        response = self.client.post(
            self.signup_url, {"email": "alum@gmail.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        profile = Profile.objects.get(user__email="alum@gmail.com")
        self.assertEqual(profile.verified_via, Profile.VerifiedVia.ADMIN_APPROVAL)
        self.assertEqual(profile.account_status, Profile.AccountStatus.UNVERIFIED)

    def test_an_approved_alum_still_has_to_verify_by_email(self):
        """Approval grants eligibility, not an active account."""
        self.approve()
        self.client.post(self.signup_url, {"email": "alum@gmail.com"}, format="json")
        self.assertEqual(len(mail.outbox), 1)
        code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)

        response = self.client.post(
            self.verify_url, {"email": "alum@gmail.com", "code": code}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        profile = Profile.objects.get(user__email="alum@gmail.com")
        self.assertEqual(profile.account_status, Profile.AccountStatus.ACTIVE)
        self.assertEqual(profile.verified_via, Profile.VerifiedVia.ADMIN_APPROVAL)

    def test_an_approved_alum_can_log_in_later(self):
        """Eligibility has to agree across endpoints, or they are stranded."""
        self.approve()
        self.client.post(self.signup_url, {"email": "alum@gmail.com"}, format="json")
        mail.outbox.clear()
        response = self.client.post(
            self.login_url, {"email": "alum@gmail.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_an_ncsu_signup_is_marked_as_verified_by_domain(self):
        self.client.post(self.signup_url, {"email": "student@ncsu.edu"}, format="json")
        profile = Profile.objects.get(user__email="student@ncsu.edu")
        self.assertEqual(profile.verified_via, Profile.VerifiedVia.NCSU_EMAIL)

    def test_the_rejection_message_does_not_mention_approval(self):
        """The 400 body must not hint that an approved-alum route exists."""
        response = self.client.post(
            self.signup_url, {"email": "stranger@gmail.com"}, format="json"
        )
        body = str(response.data).lower()
        for word in ("alum", "approv", "pending"):
            self.assertNotIn(word, body)


class AlumniApprovalFlowTests(APITestCase):
    """The admin action: idempotent, and it records who decided."""

    def setUp(self):
        from django.contrib.admin.sites import AdminSite

        from .admin import AlumniAccessRequestAdmin

        self.admin = AlumniAccessRequestAdmin(AlumniAccessRequest, AdminSite())
        self.reviewer = User.objects.create_user(
            username="reviewer@ncsu.edu", email="reviewer@ncsu.edu", is_staff=True
        )
        self.request = AlumniAccessRequest.objects.create(**VALID_REQUEST)

    def _fake_request(self):
        fake = mock.Mock()
        fake.user = self.reviewer
        return fake

    def approve(self):
        self.admin.approve_requests(
            self._fake_request(), AlumniAccessRequest.objects.filter(pk=self.request.pk)
        )
        self.request.refresh_from_db()

    def test_approving_records_the_reviewer_and_time(self):
        self.approve()
        self.assertEqual(self.request.status, AlumniAccessRequest.Status.APPROVED)
        self.assertEqual(self.request.reviewed_by, self.reviewer)
        self.assertIsNotNone(self.request.reviewed_at)

    def test_approval_makes_the_address_eligible(self):
        self.assertFalse(AlumniAccessRequest.is_approved_email("alum@gmail.com"))
        self.approve()
        self.assertTrue(AlumniAccessRequest.is_approved_email("alum@gmail.com"))

    def test_re_approving_does_not_overwrite_the_original_reviewer(self):
        self.approve()
        first_reviewer, first_time = self.request.reviewed_by, self.request.reviewed_at

        other = User.objects.create_user(
            username="other@ncsu.edu", email="other@ncsu.edu", is_staff=True
        )
        fake = mock.Mock()
        fake.user = other
        self.admin.approve_requests(
            fake, AlumniAccessRequest.objects.filter(pk=self.request.pk)
        )
        self.request.refresh_from_db()
        self.assertEqual(self.request.reviewed_by, first_reviewer)
        self.assertEqual(self.request.reviewed_at, first_time)

    def test_rejecting_revokes_eligibility(self):
        self.approve()
        self.admin.reject_requests(
            self._fake_request(), AlumniAccessRequest.objects.filter(pk=self.request.pk)
        )
        self.assertFalse(AlumniAccessRequest.is_approved_email("alum@gmail.com"))

    def _alum_account(self, email="alum@gmail.com", via=None):
        """An account created the way signup creates one for this address."""
        user = User.objects.create_user(username=email, email=email)
        return Profile.objects.create(
            user=user,
            account_status=Profile.AccountStatus.ACTIVE,
            verified_via=via or Profile.VerifiedVia.ADMIN_APPROVAL,
        )

    def reject(self):
        self.admin.reject_requests(
            self._fake_request(), AlumniAccessRequest.objects.filter(pk=self.request.pk)
        )

    def test_rejecting_suspends_the_account_the_request_let_in(self):
        """Revoking eligibility alone leaves the account reachable."""
        self.approve()
        profile = self._alum_account()
        self.reject()
        profile.refresh_from_db()
        self.assertEqual(profile.account_status, Profile.AccountStatus.SUSPENDED)

    def test_rejecting_leaves_an_ncsu_account_alone(self):
        """Their eligibility is the domain, not the request."""
        self.approve()
        profile = self._alum_account(
            email="jo@ncsu.edu", via=Profile.VerifiedVia.NCSU_EMAIL
        )
        self.reject()
        profile.refresh_from_db()
        self.assertEqual(profile.account_status, Profile.AccountStatus.ACTIVE)

    def test_rejecting_a_resubmission_does_not_revoke_an_earlier_approval(self):
        """Two requests, one still approved, so the address keeps access."""
        self.approve()
        profile = self._alum_account()
        resubmission = AlumniAccessRequest.objects.create(**VALID_REQUEST)

        self.admin.reject_requests(
            self._fake_request(),
            AlumniAccessRequest.objects.filter(pk=resubmission.pk),
        )

        profile.refresh_from_db()
        self.assertEqual(profile.account_status, Profile.AccountStatus.ACTIVE)
        self.assertTrue(AlumniAccessRequest.is_approved_email("alum@gmail.com"))

    def test_rejecting_a_request_with_no_account_yet_is_fine(self):
        """The usual case: rejected before they ever signed up."""
        self.reject()
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, AlumniAccessRequest.Status.REJECTED)

    def test_a_suspended_account_can_still_refresh_its_token(self):
        """The limit of what suspension buys, pinned so the docs stay honest.

        /auth/refresh/ is the stock TokenRefreshView: no rotation, no denylist,
        and it never looks the user up. So a suspended user keeps minting fresh
        access tokens from the refresh token they already hold. Recorded as a
        known gap in docs/security-checklist.md; if this test ever fails,
        suspension got stronger and that entry should be rewritten.
        """
        self.approve()
        profile = self._alum_account()
        refresh = RefreshToken.for_user(profile.user)
        self.reject()

        response = self.client.post(
            reverse("accounts:auth-refresh"), {"refresh": str(refresh)}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(self.client.get(reverse("accounts:me")).status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.account_status, Profile.AccountStatus.SUSPENDED)
        self.assertTrue(profile.user.is_active)  # suspension never touches this

    def test_the_clash_flag_spots_a_shared_unity_id(self):
        self.assertFalse(self.admin.unity_id_clash(self.request))
        AlumniAccessRequest.objects.create(**{**VALID_REQUEST, "email": "other@gmail.com"})
        self.assertTrue(self.admin.unity_id_clash(self.request))
