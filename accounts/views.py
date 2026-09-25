from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import PastRole, Profile

from .serializers import PastRoleSerializer, ProfileSerializer


class AppHealthView(APIView):
    def get(self, request):
        return Response({"app": "accounts", "status": "ok"})


class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer


class PastRoleViewSet(viewsets.ModelViewSet):
    queryset = PastRole.objects.all()
    serializer_class = PastRoleSerializer
