from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ConnectionRequest, Report
from .serializers import (
    IncomingConnectionRequestListSerializer,
    ConnectionRequestSerializer,
    OutgoingConnectionRequestListSerializer,
    ReportSerializer,
)


class AppHealthView(APIView):
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
        serializer.is_valid(raise_exception=True)
        recipient = serializer.validated_data["recipient"]

        if recipient == request.user:
            return Response(
                {"detail": "You cannot send a connection request to yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if ConnectionRequest.objects.filter(
            Q(sender=request.user, recipient=recipient)
            | Q(sender=recipient, recipient=request.user),
            status=ConnectionRequest.Status.PENDING,
        ).exists():
            return Response(
                {"detail": "A pending connection request already exists."},
                status=status.HTTP_409_CONFLICT,
            )

        profile = getattr(recipient, "profile", None)
        if not profile or profile.open_to_connect is not True:
            return Response(
                {"detail": "This user is not open to connection requests."},
                status=status.HTTP_403_FORBIDDEN,
            )

        connection_request = serializer.save(
            sender=request.user,
            status=ConnectionRequest.Status.PENDING,
        )
        headers = self.get_success_headers(serializer.data)
        return Response(
            self.get_serializer(connection_request).data,
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
            queryset = self.get_queryset().filter(sender=request.user).select_related(
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
    
    def patch(self, request, connection_id):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
