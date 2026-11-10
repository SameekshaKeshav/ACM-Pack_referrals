from django.contrib.auth import get_user_model
from rest_framework import serializers

from companies.models import InterviewExperience
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
        request = self.context["request"]
        if target_type == Report.TargetType.USER:
            target_exists = User.objects.filter(pk=target_id).exists()
            is_self_report = target_id == request.user.pk
        elif target_type == Report.TargetType.MESSAGE:
            target_exists = Message.objects.filter(
                pk=target_id,
                conversation__conversation_participants__user=request.user,
            ).exists()
            is_self_report = False
        else:
            target_exists = InterviewExperience.objects.filter(pk=target_id).exists()
            is_self_report = InterviewExperience.objects.filter(
                pk=target_id, author=request.user
            ).exists()

        if not target_exists:
            raise serializers.ValidationError({"target_id": "The target does not exist."})
        if is_self_report:
            raise serializers.ValidationError({"target_id": "You cannot report yourself."})
        return attrs
