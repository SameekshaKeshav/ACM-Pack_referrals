from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AppHealthView, CompanyViewSet

app_name = "companies"

router = DefaultRouter()
router.register(r"", CompanyViewSet, basename="company")

urlpatterns = [
    path("health/", AppHealthView.as_view(), name="health"),
    path("", include(router.urls)),
]
