from rest_framework import serializers

from api.models import ConnectionRequest, Report


class ConnectionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionRequest
        fields = "__all__"


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = "__all__"
