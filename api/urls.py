from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CompanyViewSet,
    ConnectionRequestViewSet,
    ConversationViewSet,
    HealthCheckView,
    MessageViewSet,
    PastRoleViewSet,
    ProfileViewSet,
    ReportViewSet,
)

router = DefaultRouter()
router.register("profiles", ProfileViewSet)
router.register("companies", CompanyViewSet)
router.register("past-roles", PastRoleViewSet)
router.register("connection-requests", ConnectionRequestViewSet)
router.register("conversations", ConversationViewSet)
router.register("messages", MessageViewSet)
router.register("reports", ReportViewSet)

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("", include(router.urls)),
]
