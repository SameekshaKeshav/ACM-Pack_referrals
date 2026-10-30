from django.contrib.auth import get_user_model
from django.core.validators import URLValidator
from rest_framework import serializers

from companies.models import Company

from .models import ConnectionRequest, ReferralRequest
from .referrals import company_ids_on_profile


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


class ConnectionRequestDetailSerializer(serializers.ModelSerializer):
    sender = ConnectionSenderSerializer(read_only=True)
    recipient = ConnectionRecipientSerializer(read_only=True)
    conversation_id = serializers.SerializerMethodField()

    class Meta:
        model = ConnectionRequest
        fields = (
            "id",
            "sender",
            "recipient",
            "message_text",
            "status",
            "created_at",
            "resolved_at",
            "conversation_id",
        )

    def get_conversation_id(self, connection_request) -> int | None:
        # ``conversation`` is the reverse one-to-one from Conversation. With
        # ``select_related("conversation")`` on the queryset this costs no extra query,
        # so a list of N requests stays one query instead of N + 1. Without it, it
        # falls back to one query per object, as before.
        conversation = getattr(connection_request, "conversation", None)
        return conversation.pk if conversation else None


HTTP_ONLY_URL = URLValidator(schemes=["http", "https"])


class ReferralCompanySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class ReferralRequestSerializer(serializers.ModelSerializer):
    """A referral ask, as sent and as shown.

    Write: ``recipient_id``, ``company_id`` (optional, must be on the recipient's
    profile), ``role_title``, ``job_url``, ``resume_url``, ``message_text``.
    The sender and status are never read from the body.
    """

    sender = ConnectionSenderSerializer(read_only=True)
    recipient = ConnectionRecipientSerializer(read_only=True)
    company = ReferralCompanySerializer(read_only=True)
    recipient_id = PositivePrimaryKeyRelatedField(
        source="recipient", queryset=User.objects.all(), write_only=True
    )
    company_id = PositivePrimaryKeyRelatedField(
        source="company",
        queryset=Company.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    role_title = serializers.CharField(max_length=255)
    job_url = serializers.URLField(
        max_length=500, required=False, allow_blank=True, validators=[HTTP_ONLY_URL]
    )
    resume_url = serializers.URLField(
        max_length=500, required=False, allow_blank=True, validators=[HTTP_ONLY_URL]
    )
    message_text = serializers.CharField(
        max_length=500, allow_blank=False, trim_whitespace=False
    )

    class Meta:
        model = ReferralRequest
        fields = (
            "id",
            "sender",
            "recipient",
            "recipient_id",
            "company",
            "company_id",
            "role_title",
            "job_url",
            "resume_url",
            "message_text",
            "status",
            "created_at",
            "resolved_at",
        )
        read_only_fields = ("id", "sender", "recipient", "company", "status",
                            "created_at", "resolved_at")

    def validate_message_text(self, value):
        if not value.strip():
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def validate(self, attrs):
        company = attrs.get("company")
        recipient = attrs.get("recipient")
        if company is not None and company.pk not in company_ids_on_profile(recipient):
            raise serializers.ValidationError(
                {"company_id": "This company is not on the recipient's profile."}
            )
        return attrs
