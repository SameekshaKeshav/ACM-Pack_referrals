from rest_framework import serializers

from companies.models import Company
from companies.serializers import CompanySerializer

from .models import PastRole, Profile, VerificationCode
from .validators import normalize_email, validate_ncsu_email


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = "__all__"


class PastRoleSerializer(serializers.ModelSerializer):
    """A role someone held at a company.

    Clients send a typed company name rather than an id; it is resolved to an
    existing company when one matches, so the directory does not fill up with
    near-duplicate spellings of the same employer.
    """

    company = CompanySerializer(read_only=True)
    company_name = serializers.CharField(write_only=True, max_length=255)

    class Meta:
        model = PastRole
        fields = (
            "id",
            "company",
            "company_name",
            "role_title",
            "start_date",
            "end_date",
        )

    def validate_company_name(self, value):
        if not Company.normalize_name(value):
            raise serializers.ValidationError("Company name cannot be blank.")
        return value

    def create(self, validated_data):
        company, _ = Company.find_or_create(validated_data.pop("company_name"))
        return PastRole.objects.create(company=company, **validated_data)

    def update(self, instance, validated_data):
        raw_name = validated_data.pop("company_name", None)
        if raw_name is not None:
            instance.company, _ = Company.find_or_create(raw_name)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField(validators=[validate_ncsu_email])

    def validate_email(self, value):
        return normalize_email(value)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(validators=[validate_ncsu_email])

    def validate_email(self, value):
        return normalize_email(value)


class VerifySerializer(serializers.Serializer):
    email = serializers.EmailField(validators=[validate_ncsu_email])
    code = serializers.CharField(
        min_length=VerificationCode.CODE_LENGTH,
        max_length=VerificationCode.CODE_LENGTH,
    )

    def validate_email(self, value):
        return normalize_email(value)
