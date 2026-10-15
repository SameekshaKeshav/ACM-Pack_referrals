from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppHealthView,
    ConnectionRequestViewSet,
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
    path("", include(router.urls)),
]
