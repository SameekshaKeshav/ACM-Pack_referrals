from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import ConnectionRequest, Report


User = get_user_model()


class PositivePrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int) or data < 1:
            raise serializers.ValidationError(
                "This field must be a positive integer.",
                code="invalid",
            )
        return super().to_internal_value(data)


class ConnectionSenderSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk", read_only=True)
    name = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()

    def get_name(self, user):
        return user.get_full_name() or user.get_username()

    def get_company(self, user):
        profile = getattr(user, "profile", None)
        company = profile.current_company if profile else None
        return company.name if company else None


class ConnectionRecipientSerializer(ConnectionSenderSerializer):
    pass


class ConnectionRequestSerializer(serializers.ModelSerializer):
    sender = ConnectionSenderSerializer(read_only=True)

    class Meta:
        model = ConnectionRequest
        fields = ("id", "sender", "recipient_id", "message_text", "status", "created_at")
        read_only_fields = ("id", "sender", "status", "created_at")

    message_text = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=500,
        trim_whitespace=False,
    )
    recipient_id = PositivePrimaryKeyRelatedField(
        source="recipient",
        queryset=User.objects.all(),
        write_only=True,
    )

    def validate_message_text(self, value):
        if not value.strip():
            raise serializers.ValidationError("This field may not be blank.")
        return value


class IncomingConnectionRequestListSerializer(serializers.ModelSerializer):
    sender = ConnectionSenderSerializer(read_only=True)

    class Meta:
        model = ConnectionRequest
        fields = ("id", "sender", "message_text", "status", "created_at")


class OutgoingConnectionRequestListSerializer(serializers.ModelSerializer):
    recipient = ConnectionRecipientSerializer(read_only=True)

    class Meta:
        model = ConnectionRequest
        fields = ("id", "recipient", "message_text", "status", "created_at")


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = "__all__"
