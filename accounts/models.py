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
