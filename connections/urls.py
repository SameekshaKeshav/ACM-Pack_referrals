from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppHealthView,
    ConnectionRequestViewSet,
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
        )
]
