from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AcceptConnectionRequestView,
    AppHealthView,
    ConnectionRequestDetailView,
    ConnectionRequestViewSet,
    DeclineConnectionRequestView,
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
