from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import ConnectionRequest, Report

from .serializers import ConnectionRequestSerializer, ReportSerializer


class AppHealthView(APIView):
    def get(self, request):
        return Response({"app": "connections", "status": "ok"})


class ConnectionRequestViewSet(viewsets.ModelViewSet):
    queryset = ConnectionRequest.objects.all()
    serializer_class = ConnectionRequestSerializer


class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
