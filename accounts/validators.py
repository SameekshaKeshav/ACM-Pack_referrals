from django.conf import settings
from rest_framework import serializers


def normalize_email(value):
    return value.strip().lower()


def is_ncsu_email(value):
    domain = settings.ALLOWED_SIGNUP_EMAIL_DOMAIN
    return normalize_email(value).endswith(f"@{domain}")


def validate_eligible_email(value):
    """Allow an @ncsu.edu address, or one an admin approved as an alum.

    NC State has no alumni verification API, so alumni are let in by hand via
    AlumniAccessRequest. Every auth endpoint shares this validator: allowing an
    approved alum to sign up but not to log in would strand them with an
    account they could never reach again.

    The message is the domain message either way, so a rejection does not say
    whether an address has a request on file.
    """
    # Imported here rather than at module scope: models imports validators.
    from .models import AlumniAccessRequest

    if is_ncsu_email(value) or AlumniAccessRequest.is_approved_email(value):
        return value
    domain = settings.ALLOWED_SIGNUP_EMAIL_DOMAIN
    raise serializers.ValidationError(f"Email must be an @{domain} address.")
