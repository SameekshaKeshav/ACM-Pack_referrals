from rest_framework import serializers

from companies.models import Company
from companies.serializers import CompanySerializer

from .models import PastRole, Profile, VerificationCode
from .validators import normalize_email, validate_ncsu_email


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = "__all__"


class DirectoryEntrySerializer(serializers.ModelSerializer):
    """One person as they appear in the directory - no bio, no contact details."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    name = serializers.SerializerMethodField()
    current_company = CompanySerializer(read_only=True)

    class Meta:
        model = Profile
        fields = (
            "user_id",
            "name",
            "major",
            "grad_year",
            "current_role",
            "current_company",
            "open_to_connect",
        )

    def get_name(self, profile):
        return profile.user.get_full_name() or profile.user.get_username()


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


class MeSerializer(serializers.ModelSerializer):
    """The caller's own profile, for GET/PATCH /api/accounts/me/.

    Past roles are included read-only so the profile page renders in one
    request, but they are written through /api/accounts/past-roles/ because
    each is its own row with its own id.
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    name = serializers.SerializerMethodField()
    first_name = serializers.CharField(
        source="user.first_name", required=False, allow_blank=True, max_length=150
    )
    last_name = serializers.CharField(
        source="user.last_name", required=False, allow_blank=True, max_length=150
    )
    current_company = CompanySerializer(read_only=True)
    current_company_name = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=255
    )
    past_roles = serializers.SerializerMethodField()
    account_status = serializers.CharField(read_only=True)

    class Meta:
        model = Profile
        fields = (
            "user_id",
            "email",
            "name",
            "first_name",
            "last_name",
            "major",
            "grad_year",
            "bio",
            "current_role",
            "current_company",
            "current_company_name",
            "open_to_connect",
            "account_status",
            "past_roles",
        )

    def get_name(self, profile):
        return profile.user.get_full_name() or profile.user.get_username()

    def get_past_roles(self, profile):
        roles = profile.user.past_roles.select_related("company").order_by("-start_date")
        return PastRoleSerializer(roles, many=True).data

    def update(self, instance, validated_data):
        user_fields = validated_data.pop("user", {})
        raw_company = validated_data.pop("current_company_name", None)

        if raw_company is not None:
            # Blank clears the current employer; anything else resolves through
            # the same dedupe path past roles use.
            instance.current_company = (
                Company.find_or_create(raw_company)[0] if raw_company.strip() else None
            )

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if user_fields:
            for field, value in user_fields.items():
                setattr(instance.user, field, value)
            instance.user.save(update_fields=list(user_fields))

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
