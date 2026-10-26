from rest_framework import serializers

from .models import Company, InterviewExperience


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "name", "industry_tag", "logo_url")


class AffiliatedUserSerializer(serializers.Serializer):
    """One person's connection to a company, from a past role or a current one."""

    user_id = serializers.IntegerField()
    name = serializers.CharField()
    major = serializers.CharField()
    grad_year = serializers.IntegerField(allow_null=True)
    role_title = serializers.CharField()
    start_date = serializers.DateField(allow_null=True)
    end_date = serializers.DateField(allow_null=True)
    is_current = serializers.BooleanField()


class CompanyDetailSerializer(CompanySerializer):
    affiliated_users = AffiliatedUserSerializer(many=True, read_only=True)

    class Meta(CompanySerializer.Meta):
        fields = CompanySerializer.Meta.fields + ("affiliated_users",)


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
