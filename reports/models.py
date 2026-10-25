from django.conf import settings
from django.db import models


class Report(models.Model):
    class TargetType(models.TextChoices):
        USER = "user", "User"
        MESSAGE = "message", "Message"

    class Reason(models.TextChoices):
        SPAM = "spam", "Spam"
        HARASSMENT = "harassment", "Harassment"
        INAPPROPRIATE_CONTENT = "inappropriate_content", "Inappropriate content"
        MISINFORMATION = "misinformation", "Misinformation"
        HATEFUL_SPEECH = "hateful_speech", "Hateful speech"
        GRAPHIC_CONTENT = "graphic_content", "Graphic content"
        FAKE_ACCOUNT = "fake_account", "Fake account"
        FRAUD_OR_SCAM = "fraud_or_scam", "Fraud or scam"
        THREATS_OR_VIOLENCE = "threats_or_violence", "Threats or violence"
        OTHER = "other", "Other"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submitted_reports",
    )
    target_type = models.CharField(max_length=10, choices=TargetType.choices)
    target_id = models.PositiveBigIntegerField()
    reason = models.CharField(max_length=30, choices=Reason.choices)
    details = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report {self.pk} ({self.target_type}:{self.target_id})"
