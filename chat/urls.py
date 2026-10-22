from django.urls import path

from .views import (
    AppHealthView,
    ConversationListView,
    ConversationMessagesView,
    MarkConversationReadView,
    SendMessageView,
)

app_name = "chat"

urlpatterns = [
    path("health/", AppHealthView.as_view(), name="health"),
    path("conversations/", ConversationListView.as_view(), name="conversation-list"),
    path(
        "conversations/<int:conversation_id>/messages/",
        ConversationMessagesView.as_view(),
        name="conversation-messages",
    ),
    path(
        "conversations/<int:conversation_id>/read/",
        MarkConversationReadView.as_view(),
        name="conversation-read",
    ),
    path("messages/", SendMessageView.as_view(), name="message-send"),
]
