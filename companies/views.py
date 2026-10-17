from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Company
from .serializers import CompanyDetailSerializer, CompanySerializer
from .services import affiliated_users


class AppHealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"app": "companies", "status": "ok"})


class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    """Companies are created implicitly when someone adds a role at one.

    Read-only on purpose: there is no reason for a client to create or rename
    a company directly, and deleting one would cascade to every PastRole that
    references it.
    """

    queryset = Company.objects.all().order_by("name")
    serializer_class = CompanySerializer

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CompanyDetailSerializer
        return CompanySerializer

    def retrieve(self, request, *args, **kwargs):
        company = self.get_object()
        data = self.get_serializer(company).data
        data["affiliated_users"] = affiliated_users(company)
        return Response(data)
