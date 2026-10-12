from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppHealthView,
    ConnectionRequestViewSet,
    ReportViewSet,
)

app_name = "connections"

router = DefaultRouter()
router.register("connection-requests", ConnectionRequestViewSet, basename="connection-request")
router.register("reports", ReportViewSet, basename="report")

urlpatterns = [
    path("health/", AppHealthView.as_view(), name="health"),
    path(
        "<int:connection_id>/accept/",
        ConnectionRequestViewSet.as_view({"patch": "patch"}),
        name="connection-request-accept"
        ),
    path(
        "",
        ConnectionRequestViewSet.as_view({"get": "list", "post": "create"}),
        name="connection-request-list-and-create"
        ),
    path("", include(router.urls)),
]
