from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Company,
    ConnectionRequest,
    Conversation,
    Message,
    PastRole,
    Profile,
    Report,
)
from .serializers import (
    CompanySerializer,
    ConnectionRequestSerializer,
    ConversationSerializer,
    MessageSerializer,
    PastRoleSerializer,
    ProfileSerializer,
    ReportSerializer,
)


class HealthCheckView(APIView):
    def get(self, request):
        return Response({"status": "ok"})


class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer


class PastRoleViewSet(viewsets.ModelViewSet):
    queryset = PastRole.objects.all()
    serializer_class = PastRoleSerializer


class ConnectionRequestViewSet(viewsets.ModelViewSet):
    queryset = ConnectionRequest.objects.all()
    serializer_class = ConnectionRequestSerializer


class ConversationViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer


class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
