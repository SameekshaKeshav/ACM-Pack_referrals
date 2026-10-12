from rest_framework import serializers

from .models import PastRole, Profile, VerificationCode
from .validators import normalize_email, validate_ncsu_email


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = "__all__"


class PastRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PastRole
        fields = "__all__"


class SignupSerializer(serializers.Serializer):
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
