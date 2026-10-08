from django.conf import settings
from rest_framework import serializers


def normalize_email(value):
    return value.strip().lower()


def validate_ncsu_email(value):
    """Reject anything outside the university domain - signup is students only."""
    domain = settings.ALLOWED_SIGNUP_EMAIL_DOMAIN
    if not normalize_email(value).endswith(f"@{domain}"):
        raise serializers.ValidationError(f"Email must be an @{domain} address.")
    return value
