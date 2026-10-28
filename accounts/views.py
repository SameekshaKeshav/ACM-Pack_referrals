import logging
import secrets
from functools import lru_cache

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from rest_framework import generics, status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PastRole, Profile, VerificationCode
from .directory import filter_directory
from .pagination import DirectoryPagination
from .throttling import CodeRequestThrottle, VerifyAttemptThrottle
from .serializers import (
    PastRoleSerializer,
    LoginSerializer,
    DirectoryEntrySerializer,
    MeSerializer,
    SignupSerializer,
    VerifySerializer,
)

User = get_user_model()

logger = logging.getLogger(__name__)

INVALID_CODE_DETAIL = "That code is invalid or has expired. Request a new one."
SEND_FAILED_DETAIL = (
    "We couldn't send your verification code right now. Please try again in a few minutes."
)


@lru_cache(maxsize=1)
def _decoy_hash():
    """A hash to compare against when no real code exists, so that an unknown
    email costs the same time as a known one."""
    return make_password(secrets.token_urlsafe(16))


def _send_code(email, code):
    """Email the code. Returns False instead of raising if the send fails
    (provider down, daily quota used up, bad key), so callers can answer with
    a proper response rather than a 500."""
    try:
        send_mail(
            subject="Your Pack Referrals verification code",
            message=(
                f"Your verification code is {code}.\n\n"
                f"It expires in {settings.VERIFICATION_CODE_TTL_MINUTES} minutes."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )
    except Exception:
        # Broad on purpose: any failure in the email provider should become a
        # friendly response. The traceback still reaches the logs and Sentry.
        logger.exception("Sending a verification code failed")
        return False
    return True


def _send_failed_response():
    return Response(
        {"detail": SEND_FAILED_DETAIL}, status=status.HTTP_503_SERVICE_UNAVAILABLE
    )


class AppHealthView(APIView):
    permission_classes = [AllowAny]  # monitoring polls this

    def get(self, request):
        return Response({"app": "accounts", "status": "ok"})


class PastRoleViewSet(viewsets.ModelViewSet):
    """Roles are readable by any verified member - that is what the company
    directory is - but only the owner may add, change or remove their own.
    """

    serializer_class = PastRoleSerializer

    def get_queryset(self):
        queryset = PastRole.objects.select_related("company", "user")
        if self.action in ("update", "partial_update", "destroy"):
            return queryset.filter(user=self.request.user)
        return queryset

    def perform_create(self, serializer):
        # Identity comes from the token, never from the request body.
        serializer.save(user=self.request.user)


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/accounts/me/ - the caller's own profile.

    Scoped to request.user, so there is no id to tamper with.
    """

    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        profile = (
            Profile.objects.select_related("user", "current_company")
            .filter(user=self.request.user)
            .first()
        )
        if profile is None:
            raise NotFound("This account has no profile.")
        return profile


class UserDirectoryView(generics.ListAPIView):
    """Browse verified members, optionally filtered.

    GET /api/accounts/users/?major=X&grad_year=Y&company_id=Z&limit=20&offset=0

    All three filters are optional and combine with AND.
    """

    serializer_class = DirectoryEntrySerializer
    pagination_class = DirectoryPagination

    def get_queryset(self):
        return filter_directory(self.request.query_params)


class SignupView(APIView):
    """Create an unverified account and email it a one-time code."""

    permission_classes = [AllowAny]  # the caller has no token yet - that is the point
    throttle_classes = [CodeRequestThrottle]

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
            if not _send_code(email, code):
                return _send_failed_response()
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

        if not _send_code(email, code):
            # The account stays unverified, so signing up again re-issues a code.
            return _send_failed_response()
        return Response(
            {"detail": "Verification code sent.", "email": email},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """Send a returning user a fresh code. There is no password to check."""

    permission_classes = [AllowAny]  # the caller has no token yet - that is the point
    throttle_classes = [CodeRequestThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            _, code = VerificationCode.issue(user)
            # A failed send is logged inside _send_code. It must not change the
            # response, or a 503 here would reveal that the account exists.
            _send_code(email, code)

        # Identical response either way, so this endpoint cannot be used to
        # discover which addresses are registered.
        return Response(
            {"detail": "If that account exists, a verification code has been sent."},
            status=status.HTTP_200_OK,
        )


class VerifyView(APIView):
    """Exchange a valid code for JWT credentials and activate the account."""

    permission_classes = [AllowAny]  # the caller has no token yet - that is the point
    throttle_classes = [VerifyAttemptThrottle]

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
        if verification.is_expired():
            return invalid
        if not verification.matches(code):
            verification.register_failed_attempt()
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
