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
