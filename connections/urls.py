from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AcceptConnectionRequestView,
    AppHealthView,
    ConnectionRequestDetailView,
    ConnectionRequestViewSet,
    DeclineConnectionRequestView,
    ReferralRequestDetailView,
    ReferralRequestListCreateView,
    ReportViewSet,
)

app_name = "connections"

router = DefaultRouter()
router.register("reports", ReportViewSet, basename="report")

urlpatterns = [
    path("health/", AppHealthView.as_view(), name="health"),
    path(
        "",
        ConnectionRequestViewSet.as_view({"get": "list", "post": "create"}),
        name="connection-request-list-and-create"
        ),
    path(
        "referrals/",
        ReferralRequestListCreateView.as_view(),
        name="referral-request-list-and-create",
    ),
    path(
        "referrals/<int:referral_id>/",
        ReferralRequestDetailView.as_view(),
        name="referral-request-detail",
    ),
    path(
        "<int:connection_id>/",
        ConnectionRequestDetailView.as_view(),
        name="connection-request-detail",
    ),
    path(
        "<int:connection_id>/accept/",
        AcceptConnectionRequestView.as_view(),
        name="connection-request-accept",
    ),
    path(
        "<int:connection_id>/decline/",
        DeclineConnectionRequestView.as_view(),
        name="connection-request-decline",
    ),
    path("", include(router.urls)),
]
