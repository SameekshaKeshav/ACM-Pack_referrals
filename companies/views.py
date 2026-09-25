from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Company

from .serializers import CompanySerializer


class AppHealthView(APIView):
    def get(self, request):
        return Response({"app": "companies", "status": "ok"})


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
