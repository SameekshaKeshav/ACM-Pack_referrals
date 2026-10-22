from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AppHealthView,
    LoginView,
    MeView,
    PastRoleViewSet,
    ProfileViewSet,
    SignupView,
    UserDirectoryView,
    VerifyView,
)

app_name = "accounts"

router = DefaultRouter()
router.register("profiles", ProfileViewSet, basename="profile")
router.register("past-roles", PastRoleViewSet, basename="past-role")

urlpatterns = [
    path("health/", AppHealthView.as_view(), name="health"),
    path("auth/signup/", SignupView.as_view(), name="auth-signup"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/verify/", VerifyView.as_view(), name="auth-verify"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("users/", UserDirectoryView.as_view(), name="user-directory"),
    path("", include(router.urls)),
]
