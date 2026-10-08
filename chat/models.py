from django.conf import settings
from django.db import models
from django.db.models.functions import Length
from django.db.models.lookups import LessThanOrEqual


class Conversation(models.Model):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ConversationParticipant",
        related_name="conversations",
    )
    created_from_connection_request = models.OneToOneField(
        "connections.ConnectionRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversation",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Conversation {self.pk}"


class ConversationParticipant(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="conversation_participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_participants",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="unique_conversation_participant",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} in conversation {self.conversation_id}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    body_text = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_status = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            # Django does not call full_clean() on save and SQLite ignores VARCHAR
            # lengths, so enforce the 2000-character cap in the database itself.
            models.CheckConstraint(
                condition=LessThanOrEqual(Length("body_text"), 2000),
                name="message_body_text_max_2000",
            ),
        ]

    def __str__(self):
        return f"Message {self.pk}"
