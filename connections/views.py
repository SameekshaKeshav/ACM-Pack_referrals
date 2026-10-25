from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from .models import Block, ConnectionRequest
from .serializers import (
    IncomingConnectionRequestListSerializer,
    ConnectionRequestSerializer,
    OutgoingConnectionRequestListSerializer,
)


class AppHealthView(APIView):
    def get(self, request):
        return Response({"app": "connections", "status": "ok"})


User = get_user_model()


class UserBlockView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        try:
            blocked_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if blocked_user == request.user:
            return Response(
                {"detail": "You cannot block yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _, created = Block.objects.get_or_create(
            blocker=request.user,
            blocked=blocked_user,
        )
        return Response(
            {"detail": "User blocked."},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, user_id):
        Block.objects.filter(blocker=request.user, blocked_id=user_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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

        if Block.objects.filter(
            Q(blocker=request.user, blocked=recipient)
            | Q(blocker=recipient, blocked=request.user)
        ).exists():
            return Response(
                {"detail": "You cannot send a connection request to this user."},
                status=status.HTTP_403_FORBIDDEN,
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
