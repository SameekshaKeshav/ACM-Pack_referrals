from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Report
from .serializers import ReportSerializer


class ReportCreateView(generics.CreateAPIView):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)
