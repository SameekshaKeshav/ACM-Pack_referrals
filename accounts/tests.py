import re
from datetime import timedelta
from unittest import mock

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
from rest_framework_simplejwt.tokens import AccessToken

from .models import Profile, VerificationCode

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
