from django.urls import path

from .views import HealthCheckView, SentryTestView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    # TEMPORARY: see SentryTestView.
    path("debug/sentry/", SentryTestView.as_view(), name="sentry-test"),
]
