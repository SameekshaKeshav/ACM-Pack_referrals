import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    class AccountStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    class VerifiedVia(models.TextChoices):
        NCSU_EMAIL = "ncsu_email", "NC State email"
        ADMIN_APPROVAL = "admin_approval", "Admin-approved alum"

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
    # How this person proved they belong. Orthogonal to account_status, which
    # is a lifecycle: an admin-approved alum still goes unverified -> active by
    # email code, and can later be suspended while staying an alum. Kept off
    # account_status deliberately - five call sites gate positively on ACTIVE
    # (directory, company pages twice, referrals twice), so a fourth status
    # would hide an alum from all of them as an empty list rather than an
    # error, while the negative SUSPENDED check in connections/views.py would
    # wave them through.
    verified_via = models.CharField(
        max_length=20,
        choices=VerifiedVia.choices,
        default=VerifiedVia.NCSU_EMAIL,
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
    attempts = models.PositiveSmallIntegerField(default=0)

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

    def register_failed_attempt(self):
        """Count a wrong guess, destroying the code once the cap is reached.

        Rate limiting is keyed by IP and so is defeated by an attacker with
        many of them. This cap is keyed by the code itself, which bounds
        guessing at VERIFICATION_MAX_ATTEMPTS out of a million regardless of
        where the requests come from.
        """
        self.attempts += 1
        if self.attempts >= settings.VERIFICATION_MAX_ATTEMPTS:
            self.delete()
            return True
        self.save(update_fields=["attempts"])
        return False

    def __str__(self):
        return f"code for {self.user.get_username()} (expires {self.expires_at:%Y-%m-%d %H:%M})"


class AlumniAccessRequest(models.Model):
    """An alum asking to be let in by hand.

    NC State has no approved way to verify alumni right now: the alumni
    directory ended with their CRM change. So signup is @ncsu.edu only, and an
    alum gets in when a human reads one of these and approves it.

    Nothing here is verifiable by the system - the Unity ID in particular is a
    signal for whoever reviews the request, never a credential. Student ID
    numbers are deliberately not collected: we could not check one, and it is
    sensitive data we would then have to protect.
    """

    # Case-insensitive on the way in, stored lowercase by save(). The model
    # field's validators run before any serializer method, so a regex demanding
    # lowercase would reject "JDoe" instead of normalizing it.
    UNITY_ID_RE = RegexValidator(
        r"^[A-Za-z][A-Za-z0-9]*$",
        "A Unity ID is letters and digits, starting with a letter, e.g. 'jdoe' or 'jdoe2'.",
    )

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    email = models.EmailField(max_length=254)
    full_name = models.CharField(max_length=150)
    unity_id = models.CharField(max_length=32, validators=[UNITY_ID_RE])
    grad_year = models.PositiveIntegerField()
    major = models.CharField(max_length=255)
    linkedin_url = models.URLField(max_length=200, blank=True)
    # Bounded at the model, not just the serializer. Profile.bio and
    # Report.reason are unbounded TextFields (issue #27); this is a public
    # endpoint, so it is not going to be the third one.
    note = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_alumni_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            # One *pending* request per address, enforced by the database.
            # Checking this in the serializer alone races: two submissions in
            # the same instant both see nothing and both insert.
            models.UniqueConstraint(
                fields=["email"],
                condition=models.Q(status="pending"),
                name="unique_pending_request_per_email",
            ),
        ]

    def __str__(self):
        return f"{self.email} ({self.status})"

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        self.unity_id = self.unity_id.strip().lower()
        super().save(*args, **kwargs)

    def other_requests_with_this_unity_id(self):
        """Requests from a different address claiming the same Unity ID.

        Two people cannot share one Unity ID, so this is either a typo or
        someone guessing at a real one. It is surfaced to the reviewer rather
        than rejected, because the honest typo is the likelier case.
        """
        return AlumniAccessRequest.objects.filter(unity_id=self.unity_id).exclude(pk=self.pk)

    @classmethod
    def is_approved_email(cls, email):
        """Whether this address has an approved request - the one source of truth.

        There is no second 'approved emails' table to drift out of step with
        the requests; approval is a status on the request itself.
        """
        return cls.objects.filter(
            email=(email or "").strip().lower(), status=cls.Status.APPROVED
        ).exists()
