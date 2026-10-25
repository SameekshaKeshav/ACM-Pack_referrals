from django.contrib.auth import get_user_model
from rest_framework import serializers

from chat.models import Message

from .models import Report


User = get_user_model()


class ReportSerializer(serializers.ModelSerializer):
    reporter = serializers.PrimaryKeyRelatedField(read_only=True)
    target_id = serializers.IntegerField(min_value=1)

    class Meta:
        model = Report
        fields = ("id", "reporter", "target_type", "target_id", "reason", "details", "created_at")
        read_only_fields = ("id", "reporter", "created_at")

    def validate(self, attrs):
        target_type = attrs["target_type"]
        target_id = attrs["target_id"]
        target_model = User if target_type == Report.TargetType.USER else Message
        if not target_model.objects.filter(pk=target_id).exists():
            raise serializers.ValidationError({"target_id": "The target does not exist."})
        return attrs
