import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError
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

        self.assertEqual(self._verify(first_code).status_code, status.HTTP_400_BAD_REQUEST)
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
            self.verify_url, {"email": EMAIL, "code": self._emailed_code()}, format="json"
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
            self.verify_url, {"email": "nobody@ncsu.edu", "code": "000000"}, format="json"
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
        self.signup_url = reverse("accounts:auth-signup")
        self.login_url = reverse("accounts:auth-login")
        self.verify_url = reverse("accounts:auth-verify")

    def _emailed_code(self):
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def _verified_account(self):
        self.client.post(self.signup_url, {"email": EMAIL}, format="json")
        self.client.post(
            self.verify_url, {"email": EMAIL, "code": self._emailed_code()}, format="json"
        )

    def test_login_sends_a_fresh_code_to_a_verified_account(self):
        self._verified_account()
        mail.outbox.clear()

        response = self.client.post(self.login_url, {"email": EMAIL}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        verify = self.client.post(
            self.verify_url, {"email": EMAIL, "code": self._emailed_code()}, format="json"
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
