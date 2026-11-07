from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Report
from .throttling import ReportThrottle
from .serializers import ReportSerializer


class ReportCreateView(generics.CreateAPIView):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ReportThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report, created = Report.objects.get_or_create(
            reporter=request.user,
            target_type=serializer.validated_data["target_type"],
            target_id=serializer.validated_data["target_id"],
            defaults={
                "reason": serializer.validated_data["reason"],
                "details": serializer.validated_data.get("details", ""),
            },
        )
        response_serializer = self.get_serializer(report)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            headers=self.get_success_headers(response_serializer.data) if created else {},
        )
