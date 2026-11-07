from rest_framework import serializers

from companies.models import Company
from companies.serializers import CompanySerializer

from .models import AlumniAccessRequest, PastRole, Profile, VerificationCode
from .validators import normalize_email, validate_eligible_email


def _resolve_company(raw_name, field):
    """Resolve a typed company name, turning a rejection into a 400.

    Company.find_or_create raises ValueError for a name that is blank or only
    a legal suffix. Left uncaught that surfaces as a 500, so it is translated
    into a field error on whichever field carried the name.
    """
    try:
        company, _ = Company.find_or_create(raw_name)
    except ValueError as exc:
        raise serializers.ValidationError({field: str(exc)}) from exc
    return company


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

    def validate(self, attrs):
        """A role cannot end before it began.

        Checked against the incoming value where present and the stored one
        otherwise, so a PATCH that moves only one of the two dates is still
        validated against the other.
        """
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be before the start date."}
            )
        return attrs

    def create(self, validated_data):
        company = _resolve_company(validated_data.pop("company_name"), "company_name")
        return PastRole.objects.create(company=company, **validated_data)

    def update(self, instance, validated_data):
        raw_name = validated_data.pop("company_name", None)
        if raw_name is not None:
            instance.company = _resolve_company(raw_name, "company_name")
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

    def validate_grad_year(self, value):
        """Catch typos. A four-digit year outside this range is a slip, not a
        student who graduated in 1800."""
        if value is not None and not (2000 <= value <= 2100):
            raise serializers.ValidationError("Must be between 2000 and 2100.")
        return value

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
                _resolve_company(raw_company, "current_company_name")
                if raw_company.strip()
                else None
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
    email = serializers.EmailField(validators=[validate_eligible_email])

    def validate_email(self, value):
        return normalize_email(value)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(validators=[validate_eligible_email])

    def validate_email(self, value):
        return normalize_email(value)


class VerifySerializer(serializers.Serializer):
    email = serializers.EmailField(validators=[validate_eligible_email])
    code = serializers.CharField(
        min_length=VerificationCode.CODE_LENGTH,
        max_length=VerificationCode.CODE_LENGTH,
    )

    def validate_email(self, value):
        return normalize_email(value)


class AlumniAccessRequestSerializer(serializers.ModelSerializer):
    """A public submission asking to be let in as an alum.

    Everything the reviewer decides on is write-only: the endpoint confirms
    receipt and nothing more, so it cannot be used to read back other
    people's requests or to check whether an address already applied.
    """

    # Declared explicitly with no validators: the conditional UniqueConstraint
    # on the model makes DRF attach a UniqueValidator here, which would reject a
    # duplicate as a field error ("...with this email already exists") before
    # validate() runs - telling the caller who has already applied. The
    # duplicate check below, plus the constraint itself, does the job quietly.
    email = serializers.EmailField(max_length=254, validators=[])

    # A hidden field no real person fills in. Bots fill every input they find.
    confirm_email = serializers.CharField(
        required=False, allow_blank=True, write_only=True
    )

    class Meta:
        model = AlumniAccessRequest
        fields = (
            "email",
            "full_name",
            "unity_id",
            "grad_year",
            "major",
            "linkedin_url",
            "note",
            "confirm_email",
        )
        extra_kwargs = {
            # status, reviewed_by and reviewed_at are not in `fields` at all, so
            # no request body can set them.
            "linkedin_url": {"required": False},
            "note": {"required": False},
        }

    def validate_email(self, value):
        return normalize_email(value)

    def validate_unity_id(self, value):
        return value.strip().lower()

    def validate_grad_year(self, value):
        if not 1900 <= value <= 2100:
            raise serializers.ValidationError("Enter a four-digit graduation year.")
        return value

    def validate(self, attrs):
        if attrs.pop("confirm_email", ""):
            # Say the same thing a duplicate says, so a bot learns nothing.
            raise serializers.ValidationError(
                {"detail": "We could not accept that request."}
            )
        email = attrs.get("email")
        if AlumniAccessRequest.objects.filter(
            email=email, status=AlumniAccessRequest.Status.PENDING
        ).exists():
            raise serializers.ValidationError(
                {"detail": "We could not accept that request."}
            )
        return attrs
