import re

from django.conf import settings
from django.db import models


class Profile(models.Model):
    class AccountStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    major = models.CharField(max_length=255, blank=True)
    grad_year = models.PositiveIntegerField(null=True, blank=True)
    bio = models.TextField(blank=True)
    current_role = models.CharField(max_length=255, blank=True)
    current_company = models.ForeignKey(
        "Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_employees",
    )
    open_to_connect = models.BooleanField(default=True)
    account_status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.UNVERIFIED,
    )

    def __str__(self):
        return self.user.get_username()


class Company(models.Model):
    SUFFIX_RE = re.compile(r"\s+(inc|llc|ltd|corp|corporation|co)$")

    name = models.CharField(max_length=255, unique=True)
    name_normalized = models.CharField(max_length=255, unique=True, editable=False)
    industry_tag = models.CharField(max_length=100, blank=True)
    logo_url = models.URLField(blank=True)

    class Meta:
        verbose_name_plural = "companies"

    @classmethod
    def normalize_name(cls, value):
        """Reduce a display name to the key used to detect duplicates."""
        normalized = " ".join(value.split()).lower().replace(".", "").replace(",", "")
        return cls.SUFFIX_RE.sub("", normalized).strip()

    def save(self, *args, **kwargs):
        self.name_normalized = self.normalize_name(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class PastRole(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="past_roles",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="affiliations",
    )
    role_title = models.CharField(max_length=255)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_username()} @ {self.company.name}"


class ConnectionRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_connection_requests",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_connection_requests",
    )
    message_text = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.sender.get_username()} → {self.recipient.get_username()} ({self.status})"


class Conversation(models.Model):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="conversations",
    )
    created_from_connection_request = models.OneToOneField(
        ConnectionRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversation",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Conversation {self.pk}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    body_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_status = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message {self.pk}"


class Report(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWED = "reviewed", "Reviewed"
        ACTIONED = "actioned", "Actioned"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_filed",
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports_received",
    )
    reported_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report {self.pk} ({self.status})"
