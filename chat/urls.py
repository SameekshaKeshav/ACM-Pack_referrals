from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AppHealthView, ConversationViewSet, MessageViewSet

app_name = "chat"

router = DefaultRouter()
router.register("conversations", ConversationViewSet, basename="conversation")
router.register("messages", MessageViewSet, basename="message")

urlpatterns = [
    path("health/", AppHealthView.as_view(), name="health"),
    path("", include(router.urls)),
]
