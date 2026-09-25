from rest_framework import serializers

from api.models import PastRole, Profile


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = "__all__"


class PastRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PastRole
        fields = "__all__"
