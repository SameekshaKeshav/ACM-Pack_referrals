from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from .models import Company, InterviewExperience
from .serializers import CompanyDetailSerializer, CompanySerializer, InterviewExperienceSerializer
from .services import affiliated_users


class AppHealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"app": "companies", "status": "ok"})


class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    """Companies are created implicitly when someone adds a role at one.

    Read-only on purpose: there is no reason for a client to create or rename
    a company directly, and deleting one would cascade to every PastRole that
    references it.
    """

    serializer_class = CompanySerializer

    def get_queryset(self):
        """All companies, or those matching ``?search=``.

        Matched against both the display name and the normalized key, so
        "Google Inc." finds the company stored as "Google" and a partial
        "goog" finds it too.
        """
        queryset = Company.objects.all().order_by("name")

        search = self.request.query_params.get("search", "").strip()
        if not search:
            return queryset

        matches = Q(name__icontains=search)
        normalized = Company.normalize_name(search)
        if normalized:
            matches |= Q(name_normalized__icontains=normalized)
        return queryset.filter(matches)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CompanyDetailSerializer
        return CompanySerializer

    def retrieve(self, request, *args, **kwargs):
        company = self.get_object()
        data = self.get_serializer(company).data
        data["affiliated_users"] = affiliated_users(company)
        return Response(data)


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
