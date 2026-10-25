from rest_framework import serializers

from .models import Company, InterviewExperience


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = "__all__"


class InterviewExperienceSerializer(serializers.ModelSerializer):
    is_mine = serializers.SerializerMethodField()
    month = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()

    class Meta:
        model = InterviewExperience
        fields = (
            "id",
            "role_title",
            "outcome",
            "difficulty",
            "process_text",
            "is_mine",
            "month",
            "year",
        )
        read_only_fields = ("id", "is_mine", "month", "year")

    def get_is_mine(self, experience):
        return experience.author_id == self.context["request"].user.id

    def get_month(self, experience):
        return experience.created_at.month

    def get_year(self, experience):
        return experience.created_at.year
