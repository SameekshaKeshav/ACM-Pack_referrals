from collections.abc import Mapping
from datetime import timedelta

from django.utils import timezone
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, mixins, viewsets
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from .blocks import blocked_user_ids
from .models import ConnectionRequest, ReferralRequest, Report
from .referrals import ReferralError, check_may_ask, create_referral_request
from .serializers import (
    ConnectionRequestDetailSerializer,
    IncomingConnectionRequestListSerializer,
    ConnectionRequestSerializer,
    OutgoingConnectionRequestListSerializer,
    ReferralRequestSerializer,
    ReportSerializer,
)
from .services import (
    ConnectionActionError,
    accept_connection_request,
    decline_connection_request,
)


class AppHealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"app": "connections", "status": "ok"})


class ConnectionRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ConnectionRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ConnectionRequest.objects.filter(
            Q(sender=self.request.user) | Q(recipient=self.request.user)
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            recipient_errors = serializer.errors.get("recipient_id", [])
            if any(error.code == "does_not_exist" for error in recipient_errors):
                return Response(
                    {"detail": "Recipient not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            raise ValidationError(serializer.errors)
        recipient = serializer.validated_data["recipient"]

        if recipient == request.user:
            return Response(
                {"detail": "You cannot send a connection request to yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if ConnectionRequest.objects.filter(
            Q(sender=request.user, recipient=recipient)
            | Q(sender=recipient, recipient=request.user),
            status__in=(
                ConnectionRequest.Status.PENDING,
                ConnectionRequest.Status.ACCEPTED,
            ),
        ).exists():
            return Response(
                {"detail": "A connection request or connection already exists."},
                status=status.HTTP_409_CONFLICT,
            )

        profile = getattr(recipient, "profile", None)
        if (
            not profile
            or profile.open_to_connect is not True
            or profile.account_status == Profile.AccountStatus.SUSPENDED
        ):
            return Response(
                {"detail": "This user is not open to connection requests."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if ConnectionRequest.objects.filter(
            Q(sender=request.user, recipient=recipient)
            | Q(sender=recipient, recipient=request.user),
            status=ConnectionRequest.Status.DECLINED,
        ).exists():
            return Response(
                {"detail": "This connection is not available."},
                status=status.HTTP_403_FORBIDDEN,
            )

        request_window_start = timezone.now() - timedelta(hours=24)
        if ConnectionRequest.objects.filter(
            sender=request.user,
            created_at__gte=request_window_start,
        ).count() >= 10:
            return Response(
                {"detail": "You have reached the connection request limit."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        connection_request = serializer.save(
            sender=request.user,
            status=ConnectionRequest.Status.PENDING,
        )
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"id": connection_request.id, "status": connection_request.status},
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def list(self, request, *args, **kwargs):
        request_type = request.query_params.get("type")
        if request_type == "incoming":
            queryset = self.get_queryset().filter(
                recipient=request.user,
                status=ConnectionRequest.Status.PENDING
            ).select_related(
                "sender",
                "sender__profile",
                "sender__profile__current_company",
            )
        elif request_type == "outgoing":
            queryset = self.get_queryset().filter(
                sender=request.user,
            ).exclude(
                status=ConnectionRequest.Status.DECLINED,
            ).select_related(
                "recipient",
                "recipient__profile",
                "recipient__profile__current_company",
            )
        else:
            return Response(
                {"detail": "type must be either incoming or outgoing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer_class = (
            IncomingConnectionRequestListSerializer
            if request_type == "incoming"
            else OutgoingConnectionRequestListSerializer
        )
        serializer = serializer_class(queryset, many=True)
        return Response(serializer.data)


class ConnectionRequestDetailView(generics.RetrieveAPIView):
    """GET /api/connections/<id>/ - only the sender and recipient can see it."""

    serializer_class = ConnectionRequestDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"
    lookup_url_kwarg = "connection_id"

    def get_queryset(self):
        return ConnectionRequest.objects.filter(
            Q(sender=self.request.user) | Q(recipient=self.request.user)
        ).select_related(
            "sender__profile__current_company",
            "recipient__profile__current_company",
            "conversation",
        )


class _ConnectionActionView(APIView):
    """Shared error handling for accept/decline."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, connection_id):
        try:
            return self.perform(request, connection_id)
        except ConnectionRequest.DoesNotExist:
            return Response(
                {"detail": "Connection request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ConnectionActionError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)

    def perform(self, request, connection_id):
        raise NotImplementedError


class AcceptConnectionRequestView(_ConnectionActionView):
    """PATCH /api/connections/<id>/accept/ - recipient accepts, a conversation is created."""

    def perform(self, request, connection_id):
        connection_request, conversation = accept_connection_request(connection_id, request.user)
        return Response(
            {
                "id": connection_request.pk,
                "status": connection_request.status,
                "conversation_id": conversation.pk,
            },
            status=status.HTTP_200_OK,
        )


class DeclineConnectionRequestView(_ConnectionActionView):
    """PATCH /api/connections/<id>/decline/ - recipient declines, no conversation."""

    def perform(self, request, connection_id):
        connection_request = decline_connection_request(connection_id, request.user)
        # Same shape as accept so the UI handles both the same way; there is never
        # a conversation after a decline.
        return Response(
            {
                "id": connection_request.pk,
                "status": connection_request.status,
                "conversation_id": None,
            },
            status=status.HTTP_200_OK,
        )


def _visible_referrals(user):
    """Referral asks ``user`` took part in, minus anyone blocked in either direction."""
    blocked = blocked_user_ids(user)
    return (
        ReferralRequest.objects.filter(Q(sender=user) | Q(recipient=user))
        .exclude(sender_id__in=blocked)
        .exclude(recipient_id__in=blocked)
        .select_related(
            "company",
            "sender__profile__current_company",
            "recipient__profile__current_company",
        )
    )


class ReferralRequestListCreateView(generics.GenericAPIView):
    """GET/POST /api/connections/referrals/ - ask a connection for a referral."""

    permission_classes = [IsAuthenticated]
    serializer_class = ReferralRequestSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "type", str, required=True, enum=["incoming", "outgoing"],
                description="Asks sent to me, or asks I sent.",
            ),
            OpenApiParameter(
                "status", str, enum=["pending", "accepted", "declined"],
                description="Only asks in this status.",
            ),
        ],
        responses=ReferralRequestSerializer(many=True),
    )
    def get(self, request):
        request_type = request.query_params.get("type")
        if request_type not in ("incoming", "outgoing"):
            return Response(
                {"detail": "type must be either incoming or outgoing."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        side = "recipient" if request_type == "incoming" else "sender"
        queryset = _visible_referrals(request.user).filter(**{side: request.user})

        wanted_status = request.query_params.get("status")
        if wanted_status:
            if wanted_status not in ReferralRequest.Status.values:
                return Response(
                    {"detail": "status must be pending, accepted or declined."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(status=wanted_status)

        return Response(ReferralRequestSerializer(queryset, many=True).data)

    @extend_schema(request=ReferralRequestSerializer, responses={201: ReferralRequestSerializer})
    def post(self, request):
        if not isinstance(request.data, Mapping):
            return Response(
                {"detail": "Send a JSON object."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Who the ask is for is settled first, so a non-connection gets 403 whatever
        # else is wrong with the body, and an unknown user gets 404.
        recipient_field = ReferralRequestSerializer().fields["recipient_id"]
        try:
            recipient = recipient_field.run_validation(
                request.data.get("recipient_id", empty)
            )
        except ValidationError as exc:
            if any(error.code == "does_not_exist" for error in exc.detail):
                return Response(
                    {"detail": "Recipient not found."}, status=status.HTTP_404_NOT_FOUND
                )
            return Response(
                {"recipient_id": exc.detail}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            check_may_ask(request.user, recipient)
            serializer = ReferralRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            referral = create_referral_request(
                request.user,
                recipient,
                company=serializer.validated_data.get("company"),
                role_title=serializer.validated_data["role_title"].strip(),
                job_url=serializer.validated_data.get("job_url", ""),
                resume_url=serializer.validated_data.get("resume_url", ""),
                message_text=serializer.validated_data["message_text"],
            )
        except ReferralError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)

        referral = _visible_referrals(request.user).get(pk=referral.pk)
        return Response(
            ReferralRequestSerializer(referral).data, status=status.HTTP_201_CREATED
        )


class ReferralRequestDetailView(generics.RetrieveAPIView):
    """GET /api/connections/referrals/<id>/ - only the sender and recipient can see it."""

    serializer_class = ReferralRequestSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"
    lookup_url_kwarg = "referral_id"

    def get_queryset(self):
        return _visible_referrals(self.request.user)


class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
