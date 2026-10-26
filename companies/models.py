import re

from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class Company(models.Model):
    SUFFIX_WORDS = frozenset({"inc", "llc", "ltd", "corp", "corporation", "co"})
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

    @classmethod
    def find_or_create(cls, raw_name):
        """Resolve a user-typed company name to a single Company row.

        Matching is on the normalized key, so "Google", "  google " and
        "Google Inc." all resolve to the same company rather than creating
        three. The first spelling seen becomes the display name.

        Returns (company, created). Raises ValueError if the name normalizes
        to nothing, which would otherwise collide with any other blank name on
        the unique constraint.
        """
        normalized = cls.normalize_name(raw_name)
        if not normalized:
            raise ValueError("Company name cannot be blank.")
        if normalized in cls.SUFFIX_WORDS:
            # "Inc." is a legal suffix, not a company. The suffix regex only
            # strips one that trails a real name, so this has to be caught here.
            raise ValueError("Company name cannot be only a legal suffix.")
        return cls.objects.get_or_create(
            name_normalized=normalized,
            defaults={"name": " ".join(raw_name.split())},
        )

    def save(self, *args, **kwargs):
        self.name_normalized = self.normalize_name(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class InterviewExperience(models.Model):
    class Outcome(models.TextChoices):
        OFFER = "offer", "Offer"
        REJECTED = "rejected", "Rejected"
        NO_RESPONSE = "no_response", "No response"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="interview_experiences",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interview_experiences",
    )
    role_title = models.CharField(max_length=255)
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    difficulty = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    process_text = models.TextField(max_length=5000)
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company.name}: {self.role_title}"
