import secrets
from functools import lru_cache

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PastRole, Profile, VerificationCode
from .serializers import (
    PastRoleSerializer,
    ProfileSerializer,
    SignupSerializer,
    VerifySerializer,
)

User = get_user_model()

INVALID_CODE_DETAIL = "That code is invalid or has expired. Request a new one."


@lru_cache(maxsize=1)
def _decoy_hash():
    """A hash to compare against when no real code exists, so that an unknown
    email costs the same time as a known one."""
    return make_password(secrets.token_urlsafe(16))


def _send_code(email, code):
    send_mail(
        subject="Your Pack Referrals verification code",
        message=(
            f"Your verification code is {code}.\n\n"
            f"It expires in {settings.VERIFICATION_CODE_TTL_MINUTES} minutes."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
    )


class AppHealthView(APIView):
    def get(self, request):
        return Response({"app": "accounts", "status": "ok"})


class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer


class PastRoleViewSet(viewsets.ModelViewSet):
    queryset = PastRole.objects.all()
    serializer_class = PastRoleSerializer


class SignupView(APIView):
    """Create an unverified account and email it a one-time code."""

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        existing = User.objects.filter(email__iexact=email).first()
        if existing is not None:
            if existing.is_active:
                return Response(
                    {"detail": "An account with that email already exists."},
                    status=status.HTTP_409_CONFLICT,
                )
            # Never verified: re-issue instead of locking the address out. This
            # covers an expired code, a failed send, and someone else having
            # claimed the address first - only the real inbox sees the code.
            _, code = VerificationCode.issue(existing)
            _send_code(email, code)
            return Response(
                {"detail": "Verification code sent.", "email": email},
                status=status.HTTP_201_CREATED,
            )

        try:
            with transaction.atomic():
                user = User(username=email, email=email, is_active=False)
                user.set_unusable_password()
                user.save()
                Profile.objects.create(user=user)
                _, code = VerificationCode.issue(user)
        except IntegrityError:
            # Two concurrent signups for the same address; the other one won.
            return Response(
                {"detail": "An account with that email already exists."},
                status=status.HTTP_409_CONFLICT,
            )

        _send_code(email, code)
        return Response(
            {"detail": "Verification code sent.", "email": email},
            status=status.HTTP_201_CREATED,
        )


class VerifyView(APIView):
    """Exchange a valid code for JWT credentials and activate the account."""

    def post(self, request):
        serializer = VerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]

        invalid = Response(
            {"detail": INVALID_CODE_DETAIL}, status=status.HTTP_400_BAD_REQUEST
        )

        user = User.objects.filter(email__iexact=email).first()
        verification = user.verification_codes.first() if user else None

        if verification is None:
            # Spend the same time hashing as a real check would, so response
            # time does not reveal whether the address is registered.
            check_password(code, _decoy_hash())
            return invalid
        if verification.is_expired() or not verification.matches(code):
            return invalid

        with transaction.atomic():
            user.is_active = True
            user.save(update_fields=["is_active"])
            profile = user.profile
            profile.account_status = Profile.AccountStatus.ACTIVE
            profile.save(update_fields=["account_status"])
            user.verification_codes.all().delete()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user_id": user.id,
                "email": user.email,
            },
            status=status.HTTP_200_OK,
        )
