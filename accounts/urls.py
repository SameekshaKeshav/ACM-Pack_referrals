from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AppHealthView, PastRoleViewSet, ProfileViewSet

app_name = "accounts"

router = DefaultRouter()
router.register("profiles", ProfileViewSet, basename="profile")
router.register("past-roles", PastRoleViewSet, basename="past-role")

urlpatterns = [
    path("health/", AppHealthView.as_view(), name="health"),
    path("", include(router.urls)),
]
