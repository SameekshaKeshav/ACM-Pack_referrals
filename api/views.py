from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """Project-wide API health; domain routes live under /api/<app>/."""

    def get(self, request):
        return Response({"status": "ok", "commit_hash": settings.COMMIT_HASH})
