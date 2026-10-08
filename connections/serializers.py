from rest_framework import serializers

from .models import ConnectionRequest, Report


class ConnectionSenderSerializer(serializers.Serializer):
    name = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()

    def get_name(self, user):
        return user.get_full_name() or user.get_username()

    def get_company(self, user):
        profile = getattr(user, "profile", None)
        company = profile.current_company if profile else None
        return company.name if company else None


class ConnectionRequestSerializer(serializers.ModelSerializer):
    sender = ConnectionSenderSerializer(read_only=True)

    class Meta:
        model = ConnectionRequest
        fields = ("id", "sender", "recipient", "message_text", "status", "created_at")
        read_only_fields = ("id", "sender", "status", "created_at")

    message_text = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ConnectionRequestListSerializer(serializers.ModelSerializer):
    sender = ConnectionSenderSerializer(read_only=True)

    class Meta:
        model = ConnectionRequest
        fields = ("id", "sender", "message_text", "status", "created_at")


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = "__all__"
