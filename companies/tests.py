from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Profile
from .models import Company, InterviewExperience


class InterviewExperienceTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme")
        self.user = self._create_user("verified", Profile.AccountStatus.ACTIVE)
        self.authenticate(self.user)
        self.url = f"/api/companies/{self.company.pk}/experiences/"
        self.payload = {
            "role_title": "Software Engineer",
            "outcome": "offer",
            "difficulty": 4,
            "process_text": "Four rounds of interviews.",
        }

    def _create_user(self, username, account_status):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(username=username)
        Profile.objects.create(user=user, account_status=account_status)
        return user

    def authenticate(self, user):
        token = AccessToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_response_is_anonymous(self):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("author", response.data)
        self.assertEqual(response.data["is_mine"], True)
        self.assertIn("month", response.data)
        self.assertIn("year", response.data)
        self.assertEqual(
            set(response.data),
            {
                "id",
                "role_title",
                "outcome",
                "difficulty",
                "process_text",
                "is_mine",
                "month",
                "year",
            },
        )

        list_response = self.client.get(self.url)
        self.assertEqual(list_response.status_code, 200)
        self.assertNotIn("author", list_response.data[0])

    def test_unverified_user_is_forbidden(self):
        user = self._create_user("unverified", Profile.AccountStatus.UNVERIFIED)
        self.authenticate(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_hidden_post_is_excluded_from_list(self):
        experience = InterviewExperience.objects.create(
            company=self.company,
            author=self.user,
            is_hidden=True,
            **self.payload,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.assertNotIn(experience.id, [item["id"] for item in response.data])

    def test_exceeding_daily_post_limit(self):
        for index in range(5):
            InterviewExperience.objects.create(
                company=self.company,
                author=self.user,
                role_title=f"Role {index}",
                outcome="rejected",
                difficulty=3,
                process_text="Process",
            )

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, 429)

    def test_author_can_delete_experience(self):
        experience = InterviewExperience.objects.create(
            company=self.company,
            author=self.user,
            **self.payload,
        )

        response = self.client.delete(
            f"{self.url}{experience.pk}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(InterviewExperience.objects.filter(pk=experience.pk).exists())
