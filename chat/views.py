from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Conversation, Message

from .serializers import ConversationSerializer, MessageSerializer


class AppHealthView(APIView):
    def get(self, request):
        return Response({"app": "chat", "status": "ok"})


class ConversationViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
