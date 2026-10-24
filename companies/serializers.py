from rest_framework import serializers

from .models import Company


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
