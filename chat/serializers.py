from rest_framework import serializers

from connections.serializers import ConnectionSenderSerializer

from .models import Message

MAX_MESSAGE_LENGTH = 2000


class MessageSerializer(serializers.ModelSerializer):
    """A message as the client sees it (see docs/api-contract-chat.md)."""

    conversation_id = serializers.IntegerField(read_only=True)
    sender_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "conversation_id", "sender_id", "body_text", "created_at", "read_status"]
        read_only_fields = fields


class SendMessageSerializer(serializers.Serializer):
    """Input for ``POST /api/chat/messages/``.

    The sender is never read from the request: the view takes it from the token.
    """

    conversation_id = serializers.IntegerField(min_value=1)
    # ``trim_whitespace=False`` keeps intentional whitespace in a valid message;
    # ``validate_body_text`` still rejects a message that is only whitespace.
    body_text = serializers.CharField(max_length=MAX_MESSAGE_LENGTH, trim_whitespace=False)

    def validate_body_text(self, value):
        if not value.strip():
            raise serializers.ValidationError("Message cannot be blank.")
        return value


class LastMessageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sender_id = serializers.IntegerField()
    body_text = serializers.CharField()
    created_at = serializers.DateTimeField()


class ConversationListSerializer(serializers.Serializer):
    """One row of the sidebar. Expects the annotations added by the list view."""

    id = serializers.IntegerField()
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    updated_at = serializers.DateTimeField()
    unread_count = serializers.IntegerField()

    def get_other_user(self, conversation) -> dict | None:
        me = self.context["request"].user
        for participant in conversation.conversation_participants.all():
            if participant.user_id != me.pk:
                return ConnectionSenderSerializer(participant.user).data
        return None

    def get_last_message(self, conversation) -> dict | None:
        if conversation.last_message_id is None:
            return None
        return LastMessageSerializer(
            {
                "id": conversation.last_message_id,
                "sender_id": conversation.last_message_sender_id,
                "body_text": conversation.last_message_body,
                "created_at": conversation.last_message_created_at,
            }
        ).data


class MarkReadResultSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField()
    updated_count = serializers.IntegerField()
