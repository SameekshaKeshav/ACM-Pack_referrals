import re

from django.db import models


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
