from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from chat.models import Conversation, ConversationParticipant, Message

from .models import Report


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

    def test_invalid_target_type_reason_and_long_details_are_rejected(self):
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
