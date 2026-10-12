import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


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
        "companies.Company",
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


class PastRole(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="past_roles",
    )
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="affiliations",
    )
    role_title = models.CharField(max_length=255)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_username()} @ {self.company.name}"


class VerificationCode(models.Model):
    """A single-use email verification code. Only the hash is stored."""

    CODE_LENGTH = 6

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_codes",
    )
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def issue(cls, user):
        """Replace any outstanding codes and return (instance, plaintext code)."""
        cls.objects.filter(user=user).delete()
        code = f"{secrets.randbelow(10 ** cls.CODE_LENGTH):0{cls.CODE_LENGTH}d}"
        instance = cls.objects.create(
            user=user,
            code_hash=make_password(code),
            expires_at=timezone.now()
            + timedelta(minutes=settings.VERIFICATION_CODE_TTL_MINUTES),
        )
        return instance, code

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def matches(self, raw_code):
        return check_password(raw_code, self.code_hash)

    def __str__(self):
        return f"code for {self.user.get_username()} (expires {self.expires_at:%Y-%m-%d %H:%M})"
