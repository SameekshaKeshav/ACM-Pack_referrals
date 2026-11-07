from django.urls import path

from .views import (
    AcceptConnectionRequestView,
    AppHealthView,
    ConnectionRequestDetailView,
    ConnectionRequestViewSet,
    DeclineConnectionRequestView,
    ReferralRequestDetailView,
    ReferralRequestListCreateView,
    UserBlockView,
)

app_name = "connections"

urlpatterns = [
    path("health/", AppHealthView.as_view(), name="health"),
    path(
        "users/<int:user_id>/block/",
        UserBlockView.as_view(),
        name="user-block",
    ),
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
]
