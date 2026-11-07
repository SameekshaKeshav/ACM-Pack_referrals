from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from companies.models import Company, InterviewExperience
from chat.models import Conversation, ConversationParticipant, Message

from .models import Report
from .throttling import ReportThrottle


User = get_user_model()


class ReportCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.reporter = User.objects.create_user(username="reporter")
        self.body_user = User.objects.create_user(username="body-user")
        self.conversation = Conversation.objects.create()
        ConversationParticipant.objects.create(
            conversation=self.conversation,
            user=self.reporter,
        )
        self.message = Message.objects.create(
            conversation=self.conversation,
            sender=self.reporter,
            body_text="Message to report",
        )
        self.outsider = User.objects.create_user(username="outsider")

    def authenticate(self, user):
        token = AccessToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_valid_jwt_creates_report_with_token_user_as_reporter(self):
        self.authenticate(self.reporter)
        response = self.client.post(
            "/api/reports/",
            {
                "reporter": self.body_user.pk,
                "target_type": "user",
                "target_id": self.body_user.pk,
                "reason": "spam",
                "details": "Repeated unsolicited messages.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        report = Report.objects.get()
        self.assertEqual(report.reporter, self.reporter)
        self.assertNotEqual(report.reporter, self.body_user)
        self.assertEqual(report.target_type, Report.TargetType.USER)
        self.assertEqual(report.target_id, self.body_user.pk)
        self.assertEqual(report.reason, Report.Reason.SPAM)
        self.assertEqual(report.details, "Repeated unsolicited messages.")

    def test_message_target_and_optional_details(self):
        self.authenticate(self.reporter)
        response = self.client.post(
            "/api/reports/",
            {
                "target_type": "message",
                "target_id": self.message.pk,
                "reason": "harassment",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Report.objects.get().details, "")

    def test_message_report_requires_conversation_participation(self):
        self.authenticate(self.outsider)
        payload = {
            "target_type": "message",
            "reason": "harassment",
        }
        inaccessible = self.client.post(
            "/api/reports/",
            {**payload, "target_id": self.message.pk},
            format="json",
        )
        nonexistent = self.client.post(
            "/api/reports/",
            {**payload, "target_id": self.message.pk + 9999},
            format="json",
        )

        self.assertEqual(inaccessible.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(nonexistent.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(inaccessible.json(), nonexistent.json())
        self.assertEqual(
            inaccessible.json()["target_id"],
            ["The target does not exist."],
        )

    def test_report_throttle(self):
        cache.clear()
        self.addCleanup(cache.clear)
        targets = [
            User.objects.create_user(username=f"report-target-{index}")
            for index in range(3)
        ]
        self.authenticate(self.reporter)
        payload = {
            "target_type": "user",
            "reason": "spam",
        }

        with mock.patch.object(
            ReportThrottle,
            "THROTTLE_RATES",
            {"report_create": "2/min"},
        ):
            responses = [
                self.client.post(
                    "/api/reports/",
                    {**payload, "target_id": target.pk},
                    format="json",
                )
                for target in targets
            ]

        self.assertEqual(
            [response.status_code for response in responses],
            [
                status.HTTP_201_CREATED,
                status.HTTP_201_CREATED,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )
        self.assertEqual(Report.objects.count(), 2)

    def test_duplicate_report_is_ignored(self):
        self.authenticate(self.reporter)
        payload = {
            "target_type": "user",
            "target_id": self.body_user.pk,
            "reason": "spam",
        }

        first_response = self.client.post("/api/reports/", payload, format="json")
        second_response = self.client.post("/api/reports/", payload, format="json")
        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(Report.objects.count(), 1)

    def test_self_report_is_rejected(self):
        self.authenticate(self.reporter)
        response = self.client.post(
            "/api/reports/",
            {
                "target_type": "user",
                "target_id": self.reporter.pk,
                "reason": "spam",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["target_id"], ["You cannot report yourself."])

    def test_interview_experience_can_be_reported(self):
        company = Company.objects.create(name="Reportable Co")
        experience = InterviewExperience.objects.create(
            company=company,
            author=self.body_user,
            role_title="Engineer",
            outcome=InterviewExperience.Outcome.REJECTED,
            difficulty=3,
            process_text="A process.",
        )
        self.authenticate(self.reporter)
        response = self.client.post(
            "/api/reports/",
            {
                "target_type": "experience",
                "target_id": experience.pk,
                "reason": "other",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Report.objects.get().target_type,
            Report.TargetType.EXPERIENCE,
        )

    def test_endpoint_requires_jwt_authentication(self):
        response = self.client.post(
            "/api/reports/",
            {
                "target_type": "user",
                "target_id": self.body_user.pk,
                "reason": "spam",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Report.objects.count(), 0)

    def test_invalid_fields(self):
        self.authenticate(self.reporter)
        base_payload = {
            "target_type": "user",
            "target_id": self.body_user.pk,
            "reason": "spam",
        }
        for field, value in (
            ("target_type", "company"),
            ("reason", "not-a-reason"),
            ("details", "x" * 1001),
        ):
            with self.subTest(field=field):
                payload = {**base_payload, field: value}
                response = self.client.post(
                    "/api/reports/",
                    payload,
                    format="json",
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Report.objects.count(), 0)
