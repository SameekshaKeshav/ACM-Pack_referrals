from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppHealthView,
    CompanyViewSet,
    InterviewExperienceDetailView,
    InterviewExperienceView,
)

app_name = "companies"

router = DefaultRouter()
router.register(r"", CompanyViewSet, basename="company")

urlpatterns = [
    path("health/", AppHealthView.as_view(), name="health"),
    path(
        "<int:company_id>/experiences/",
        InterviewExperienceView.as_view(),
        name="interview-experience-list",
    ),
    path(
        "<int:company_id>/experiences/<int:experience_id>/",
        InterviewExperienceDetailView.as_view(),
        name="interview-experience-detail",
    ),
    path("", include(router.urls)),
]
