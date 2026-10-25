from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


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


class ReferralRequest(models.Model):
    """A specific ask for a referral, sent to someone the sender is already connected to.

    This is deliberately not a ``ConnectionRequest``: accepting a connection opens a
    conversation, whereas the two people already have one. A referral ask only records
    the role being asked about and the recipient's answer.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_referral_requests",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_referral_requests",
    )
    # Must be a company on the recipient's profile (current or past); checked by the
    # serializer. Optional, because an ask can be about a role the recipient could
    # still pass along without working there.
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referral_requests",
    )
    role_title = models.CharField(max_length=255)
    job_url = models.URLField(max_length=500, blank=True)
    resume_url = models.URLField(max_length=500, blank=True)
    message_text = models.CharField(max_length=500)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            # One open ask per person, company and role, ignoring case. This is the
            # backstop for the 409 the API returns (which also ignores case), so two
            # simultaneous requests cannot both succeed whatever capitalisation each
            # used. A NULL company never compares equal, so it gets its own constraint.
            models.UniqueConstraint(
                Lower("role_title"), "sender", "recipient", "company",
                condition=models.Q(status="pending", company__isnull=False),
                name="unique_pending_referral_with_company",
            ),
            models.UniqueConstraint(
                Lower("role_title"), "sender", "recipient",
                condition=models.Q(status="pending", company__isnull=True),
                name="unique_pending_referral_without_company",
            ),
            models.CheckConstraint(
                condition=~models.Q(sender=models.F("recipient")),
                name="referral_not_to_self",
            ),
        ]

    def __str__(self):
        return (
            f"{self.sender.get_username()} → {self.recipient.get_username()}: "
            f"{self.role_title} ({self.status})"
        )


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
        "chat.Message",
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


class Block(models.Model):
    """One user has blocked another. SAMPLE VERSION so chat can honour blocks.

    Thomas (BE2) owns this: replace or extend it freely (extra fields, the block and
    unblock endpoints, the check in ``POST /api/connections/``). Chat only relies on
    ``blocked_user_ids()`` in ``connections/blocks.py``, so keep that function working
    and nothing in ``chat/`` needs to change. A block is soft: no messages are deleted.
    """

    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_made",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_block"),
            models.CheckConstraint(
                condition=~models.Q(blocker=models.F("blocked")),
                name="block_not_self",
            ),
        ]

    def __str__(self):
        return f"{self.blocker.get_username()} blocked {self.blocked.get_username()}"
