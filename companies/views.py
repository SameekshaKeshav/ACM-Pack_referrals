from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from .models import Company, InterviewExperience
from .serializers import CompanySerializer, InterviewExperienceSerializer


class AppHealthView(APIView):
    def get(self, request):
        return Response({"app": "companies", "status": "ok"})


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer


class InterviewExperiencePermission(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        profile = getattr(request.user, "profile", None)
        return (
            profile is not None
            and profile.account_status == Profile.AccountStatus.ACTIVE
        )


class InterviewExperienceView(APIView):
    permission_classes = [InterviewExperiencePermission]

    def get_company(self, company_id):
        return get_object_or_404(Company, pk=company_id)

    def get(self, request, company_id):
        company = self.get_company(company_id)
        experiences = InterviewExperience.objects.filter(
            company=company,
            is_hidden=False,
        )
        serializer = InterviewExperienceSerializer(
            experiences,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)

    def post(self, request, company_id):
        company = self.get_company(company_id)
        today = timezone.localdate()
        if InterviewExperience.objects.filter(
            author=request.user,
            created_at__date=today,
        ).count() >= 5:
            return Response(
                {"detail": "You have reached the daily interview experience limit."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = InterviewExperienceSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        experience = serializer.save(company=company, author=request.user)
        return Response(
            InterviewExperienceSerializer(
                experience,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class InterviewExperienceDetailView(APIView):
    permission_classes = [InterviewExperiencePermission]

    def delete(self, request, company_id, experience_id):
        experience = get_object_or_404(
            InterviewExperience,
            pk=experience_id,
            company_id=company_id,
        )
        if experience.author_id != request.user.id:
            return Response(
                {"detail": "You can only delete your own interview experiences."},
                status=status.HTTP_403_FORBIDDEN,
            )
        experience.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
